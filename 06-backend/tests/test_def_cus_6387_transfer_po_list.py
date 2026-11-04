"""The PO's transfer list of 2026-09-23 — what a SALE now does, backend half.

Rulings (decision log 2026-09-23, the TRF-02 entries; `BR-CUS-1081` amended):

  * **T1 / `DEF-CUS-6387`** — an account with no customer linked is SOLD, and
    the seller is recorded by the name on the account. The refusal
    `from_account_has_no_customer_entity` is retired.
  * **T1 / `DEF-CUS-6386`** — a buyer FOUND and LINKED needs no identifier
    re-typed; the found customer IS the buyer.
  * **T3 / `DEF-CUS-6393`** — *"At the sale, the seller's email, phone and
    autopay are removed. The buyer's are used if given; otherwise bills go by
    post to the service address."*
  * **T4 / `DEF-CUS-6391`** — *"Store a second person on the account (name,
    email, phone), shown on the account page"*.
  * **T2 / `DEF-CUS-6394`** — *"in case of master account - not in case of
    regualr account - (a) The sale makes the buyer the property's owner."*
  * **`DEF-CUS-6395`** — a refusal is served on the step where its cause is
    picked (`POST /transfers/account-preview`, and `buyer-preview` with the
    account), never only at the commit.
  * **`DEF-CUS-5182`** — the cycle, period, next bill and ledger start are
    served rather than hard-coded *"Not available yet"*.

Worked, as the PO's own sample: an account held by nobody (A-11512, *Hollis,
Marcus*, 61 Larkspur Way) sold to a buyer who gave a phone and no email.
"""


import pytest

from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.customers import transfers
from apps.metering import models as metering_models
from apps.metering import premises_owners
from core import errors

from tests.br_cus_1114_fixtures import top_up_homes
from tests import identity_fixtures
from tests.test_cr058_w4_transfer_reassigns import _sell, _sold_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,  # noqa: F401 — autouse BE-03 capture sink
    brazos,
    make_premises,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: The PO's buyer, identified by a phone and nothing else, and no email given.
TIM = {"display_name": "Aiden, Tim", "kind": "person", "identity": {"phone": "+1-555-0144"}}


def _unlink(account):
    """The legacy state the sample tenant's A-11512 is in: an account and its
    contact, and NO `customer_accounts` row. It can no longer be made through
    the front door (`BR-CUS-1024`), so it is made the way the sample seed has it."""
    customers_models.CustomerAccount.objects.filter(account_id=account.id).delete()


def _seller_reach(account, *, email="marisol@example.invalid", autopay=True):
    """Give the seller an email, a mailing address and autopay to lose."""
    customers_models.Contact.objects.filter(account_id=account.id).update(
        email=email, phone="+1-555-0101", gov_id_last4="4417"
    )
    customers_models.Address.objects.create(
        tenant_id=account.tenant_id,
        account=account,
        kind="mailing",
        line1="9 Seller Street",
        city="Katy",
        state="TX",
        postal_code="77449",
    )
    customers_models.Account.objects.filter(id=account.id).update(autopay=autopay)


# ── T1 · the seller with nobody on file ─────────────────────────────────────


def test_an_account_with_no_customer_is_sold_and_the_seller_is_recorded_by_name(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        _unlink(account)
        row = _sell(marcus, account, buyer=TIM)
        transfer = transfers.Transfer.objects.get(id=row["id"])
        assert transfer.customer_id is None, "nobody was on file, and nobody is invented"
        assert transfer.seller_name == "Alvarez, Marisol", (
            "the seller is recorded by the name on the account (the contact's)"
        )
        assert row["seller_name"] == "Alvarez, Marisol"
        live = list(customers_models.CustomerAccount.live(tenant_id=brazos.id, account=account))
        assert [link.customer.display_name for link in live] == ["Aiden, Tim"]


def test_the_retired_refusal_is_gone_not_merely_unused():
    assert not hasattr(transfers, "REFUSAL_NO_CUSTOMER")


def test_a_found_customer_is_linked_without_an_identifier_retyped(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        _p2, _u2, other = _sold_account(marcus, brazos, label="12 Found Road")
        found = customers_models.CustomerAccount.live(
            tenant_id=brazos.id, account=other
        ).first().customer
        buyer = {"display_name": found.display_name, "kind": found.kind, "identity": {},
                 "customer_id": str(found.id)}
        row = _sell(marcus, account, buyer=buyer)
        assert row["reassignment"]["to_customer_id"] == str(found.id), (
            "the found customer IS the buyer — no second customer is minted"
        )


def test_an_id_that_is_not_this_tenants_customer_earns_no_exemption(brazos, marcus):
    """Only a REAL customer of this tenant exempts the buyer from an identifier.
    An id that is unknown, malformed or another tenant's (HR-1: the same fact
    from here) is never refused BY ITSELF — `DEF-CUS-5974`'s contract says a
    half-typed id is *"not recognised, never a 500"* — it simply earns nothing,
    so the ordinary identifier rule refuses the buyer by name."""
    with tenant_ctx(brazos):
        for customer_id in ("00000000-0000-0000-0000-000000000000", "nope"):
            with pytest.raises(errors.BizError) as refused:
                transfers._validated_buyer(
                    {"display_name": "X", "kind": "person", "identity": {},
                     "customer_id": customer_id}
                )
            assert refused.value.params["reason"] == transfers.REFUSAL_BUYER_NOT_IDENTIFIED


# ── T3 · the seller's reach ends at the sale ───────────────────────────────


def test_the_sellers_email_phone_mailing_address_and_autopay_are_removed(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        _seller_reach(account)
        row = _sell(marcus, account, buyer={**TIM, "applicant_phone": "+1-555-0144"})
        contact = customers_models.Contact.objects.get(
            account_id=account.id, deleted_at__isnull=True, is_primary=True
        )
        assert contact.full_name == "Aiden, Tim"
        assert contact.email is None, "no email given: the seller's is removed, not kept"
        assert contact.phone == "+1-555-0144"
        assert contact.gov_id_last4 is None, "the seller's last four do not stay on the buyer's row"
        assert not customers_models.Address.objects.filter(
            account_id=account.id, kind="mailing", deleted_at__isnull=True
        ).exists(), "no mailing address given: bills go by post to the service address"
        account.refresh_from_db()
        assert account.autopay is False, "the seller's bank instruction stops at the sale"
        written = set(row["buyer_carried"]["written"])
        assert {"contact", "mailing_address_removed", "autopay_removed"} <= written
        codes = {gap["code"] for gap in row["unavailable"]}
        assert "contact_details_still_the_sellers" not in codes
        assert "mailing_address_still_the_sellers" not in codes


def test_the_buyers_mailing_address_replaces_the_sellers(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        _seller_reach(account)
        buyer = {**TIM, "applicant_email": "tim@example.invalid",
                 "mailing_address": {"line1": "4 Buyer Court", "city": "Katy",
                                     "state": "TX", "postal_code": "77450"}}
        _sell(marcus, account, buyer=buyer)
        rows = list(customers_models.Address.objects.filter(
            account_id=account.id, kind="mailing", deleted_at__isnull=True))
        assert [row.line1 for row in rows] == ["4 Buyer Court"]
        contact = customers_models.Contact.objects.get(account_id=account.id, is_primary=True,
                                                       deleted_at__isnull=True)
        assert contact.email == "tim@example.invalid"


# ── T4 · the co-applicant is stored ─────────────────────────────────────────


def test_a_co_applicant_is_stored_as_the_accounts_second_person(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        buyer = {**TIM, "co_applicant_name": "Aiden, Maya",
                 "co_applicant_email": "maya@example.invalid", "co_applicant_phone": "+1-555-0145"}
        row = _sell(marcus, account, buyer=buyer)
        second = customers_models.Contact.objects.get(
            account_id=account.id, is_primary=False, deleted_at__isnull=True
        )
        assert (second.full_name, second.email, second.phone) == (
            "Aiden, Maya", "maya@example.invalid", "+1-555-0145")
        assert "co_applicant" in row["buyer_carried"]["written"]
        assert "co_applicant_captured_and_not_stored" not in {g["code"] for g in row["unavailable"]}


def test_the_sellers_second_person_leaves_with_the_seller(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        customers_services.set_account_co_applicant(
            marcus, account.id, {"full_name": "Alvarez, Ruben"})
        _sell(marcus, account, buyer=TIM)
        assert not customers_models.Contact.objects.filter(
            account_id=account.id, is_primary=False, deleted_at__isnull=True).exists()


def test_the_account_page_door_edits_and_removes_the_co_applicant(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        detail = customers_services.update_account_co_applicant(
            marcus, account.id, {"full_name": "Aiden, Maya", "phone": "+1-555-0145"})
        names = [(c["full_name"], c["is_primary"]) for c in detail["contacts"]]
        assert ("Aiden, Maya", False) in names
        detail = customers_services.update_account_co_applicant(
            marcus, account.id, {"email": "maya@example.invalid"})
        second = [c for c in detail["contacts"] if not c["is_primary"]]
        assert second[0]["phone"] == "+1-555-0145" and second[0]["email"] == "maya@example.invalid"
        detail = customers_services.update_account_co_applicant(marcus, account.id, {"full_name": ""})
        assert [c for c in detail["contacts"] if not c["is_primary"]] == []
        # ⚠ This case refused `dob` until DEF-CUS-10253 (PO 2026-10-18, image
        # 08-edit.png: the co-applicant dialog takes a date of birth). A key
        # outside the door is still refused by name — the identifier stays out.
        with pytest.raises(errors.ValidationError):
            customers_services.update_account_co_applicant(marcus, account.id, {"gov_id_last4": "4471"})


# ── T2 · the property's owner moves ONLY for a master account ───────────────


def test_a_regular_account_sale_leaves_the_owner_and_states_nothing(brazos, marcus):
    with tenant_ctx(brazos):
        premises, _unit, account = _sold_account(marcus, brazos)
        owner = premises_owners.create_premises_owner(marcus, {"name": "Old Owner LLC",
                                                               "category": "landlord"})
        premises_owners.match_premises_owner(marcus, premises["id"], {"owner_id": owner["id"]})
        row = _sell(marcus, account, buyer=TIM)
        assert row["premises_owner"]["state"] == "unchanged"
        assert str(metering_models.Premises.objects.get(id=premises["id"]).owner_id) == owner["id"]
        codes = {gap["code"] for gap in row["unavailable"]}
        assert not {"premises_owner_record_not_updated", "premises_owner_not_moved"} & codes


def _master(actor, premises):
    # `BR-CUS-1114` (PO 2026-10-02) — two or more homes before a master.
    top_up_homes(actor, premises["id"])
    return customers_services.create_master_account(
        actor,
        {
            "premises_id": str(premises["id"]),
            "account_type": "residential",
            "opened_at": "2026-07-01",
            "contact": {"full_name": "Old Owner LLC"},
            "customer": identity_fixtures.customer_block("Old Owner LLC", kind="company"),
        },
    )


def test_selling_the_master_account_makes_the_buyer_the_premises_owner(brazos, marcus):
    with tenant_ctx(brazos):
        premises = make_premises(marcus, services_available=["electric"])
        owner = premises_owners.create_premises_owner(marcus, {"name": "Old Owner LLC",
                                                               "category": "landlord"})
        premises_owners.match_premises_owner(marcus, premises["id"], {"owner_id": owner["id"]})
        master = _master(marcus, premises)
        premises_owners.link_owner_master_account(marcus, owner["id"], master["id"])
        account = customers_models.Account.objects.get(id=master["id"])
        row = _sell(marcus, account, buyer=TIM)
        assert row["premises_owner"]["state"] == "moved"
        row_p = metering_models.Premises.objects.get(id=premises["id"])
        new_owner = metering_models.PremisesOwner.objects.get(id=row_p.owner_id)
        assert new_owner.name == "Aiden, Tim"
        assert new_owner.category.code == "landlord", "the category is carried, never guessed"
        assert str(new_owner.master_account_id) == str(account.id)
        old = metering_models.PremisesOwner.objects.get(id=owner["id"])
        assert old.master_account_id is None, "the seller's party is no longer billed through it"


def test_a_master_sale_with_no_typed_owner_states_why_it_did_not_move(brazos, marcus):
    with tenant_ctx(brazos):
        premises = make_premises(marcus, services_available=["electric"])
        master = _master(marcus, premises)
        # The master door types an owner for the address; the legacy state this
        # case is about is an address with NO typed owner, so it is cleared.
        metering_models.Premises.objects.filter(id=premises["id"]).update(owner_id=None)
        account = customers_models.Account.objects.get(id=master["id"])
        row = _sell(marcus, account, buyer=TIM)
        assert row["premises_owner"]["state"] == "not_moved"
        gaps = [gap for gap in row["unavailable"] if gap["code"] == "premises_owner_not_moved"]
        assert gaps and gaps[0]["reason"] == premises_owners.OWNER_NOT_MOVED_NO_CATEGORY


# ── `DEF-CUS-6395` · the refusal on the step where its cause is picked ──────


def test_the_account_preview_refuses_an_account_already_being_sold(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        preview = transfers.preview_account(marcus, {"from_account_id": str(account.id)})
        assert preview["refusal"] is None
        transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        preview = transfers.preview_account(marcus, {"from_account_id": str(account.id)})
        assert preview["refusal"]["code"] == transfers.REFUSAL_ALREADY_BEING_SOLD
        with pytest.raises(errors.BizError) as caught:
            transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        assert caught.value.params["reason"] == transfers.REFUSAL_ALREADY_BEING_SOLD, (
            "the commit refuses by the same function, by name — never an IntegrityError"
        )


def test_the_account_preview_serves_the_seller_and_the_ledger_start(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        preview = transfers.preview_account(marcus, {"from_account_id": str(account.id)})
        assert preview["seller"]["name"] == "Alvarez, Marisol"
        assert preview["seller_name"] == "Alvarez, Marisol"
        assert preview["is_master"] is False
        assert preview["ledger_since"] == "2026-07-01"
        # No cycle is set up in this fixture: the honest answer is None, never a
        # guessed 30-day month.
        assert preview["billing_cycle"] is None and preview["next_bill_on"] is None
        _unlink(account)
        preview = transfers.preview_account(marcus, {"from_account_id": str(account.id)})
        assert preview["seller"] is None and preview["seller_name"] == "Alvarez, Marisol"


def test_the_buyer_preview_refuses_the_sellers_own_customer_on_step_2(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        seller = customers_models.CustomerAccount.live(
            tenant_id=brazos.id, account=account).first().customer
        block = {"display_name": seller.display_name, "kind": "person", "identity": {},
                 "customer_id": str(seller.id)}
        preview = transfers.preview_buyer(marcus, {"customer": block,
                                                   "from_account_id": str(account.id)})
        assert preview["refusal"]["code"] == transfers.REFUSAL_BUYER_IS_THE_SELLER
        assert transfers.preview_buyer(marcus, {"customer": TIM,
                                                "from_account_id": str(account.id)})["refusal"] is None


# ── the messages: the field-visit text only when a visit was asked for ──────


def test_no_visit_needed_queues_no_meter_visit_text(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        _unlink(account)
        row = _sell(marcus, account, buyer=TIM)
        templates = [m.get("template_code") for m in row["messages"]]
        assert "transfer_field_visit_sms" not in templates
        parties = {m.get("party") for m in row["messages"]}
        assert parties == {"buyer", "seller"}, (
            "a seller with no customer row is still written to, by the name on the account"
        )


# ── Item 12 · the ONE field-visit table (`DEF-CUS-6392`) ────────────────────


def _visit_catalogue(tenant):
    """One job type and one crew — shapes, not figures (B14 rule 37). Ranks far
    above any seed, because `rank` is unique per tenant."""
    from apps.work import models as work_models

    normal = work_models.WorkPriority.objects.create(
        tenant=tenant, code="normal-6392", name="Normal (test)", rank=913, sla_hours=72
    )
    exchange = work_models.WorkOrderType.objects.create(
        tenant=tenant, code="MX-6392", name="Meter exchange — residential", default_priority=normal
    )
    crew = work_models.Crew.objects.create(tenant=tenant, name="Crew T (2)", kind="crew")
    return exchange, crew


def _sell_with_visit(actor, account, field_visit, *, buyer=None):
    started = transfers.start_transfer(actor, {"from_account_id": str(account.id)})
    transfers.set_new_customer(actor, started["id"], {"customer": buyer or TIM})
    transfers.set_sale_date(actor, started["id"], {"sold_on": "2026-09-24"})
    transfers.acknowledge_money(actor, started["id"])
    return transfers.reassign_account(
        actor, started["id"], {"customer": buyer or TIM, "field_visit": field_visit}
    )


def test_a_row_added_on_the_field_visit_table_is_raised_when_the_sale_commits(brazos, marcus):
    """The PO's approved table (*"this is correct"*): Meter exchange —
    residential · Normal · 24-Sep-26 · a crew · *Check meter at sale*. Raised
    AFTER the commit, on the SAME account, read back out of `work_orders`."""
    from apps.work import connection_models as work_tables

    with tenant_ctx(brazos):
        exchange, crew = _visit_catalogue(brazos)
        _premises, _unit, account = _sold_account(marcus, brazos)
        row = _sell_with_visit(
            marcus,
            account,
            {"orders": [{"type_id": str(exchange.id), "due_on": "2026-09-24",
                         "crew_id": str(crew.id), "note": "Check meter at sale"}]},
        )
        assert [order["name"] for order in row["work_orders"]] == ["Meter exchange — residential"]
        order = work_tables.WorkOrder.objects.get(pk=row["work_orders"][0]["id"])
        assert order.technician_notes == "Check meter at sale"
        assert row["field_visit_declined"] is False
        # The visit text is queued because a visit WAS asked.
        assert "transfer_field_visit_sms" in {m.get("template_code") for m in row["messages"]}


def test_no_visit_needed_raises_nothing_and_sends_no_visit_text(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        row = _sell_with_visit(marcus, account, {"none": True})
        assert row["work_orders"] == []
        assert row["field_visit_declined"] is True
        assert "transfer_field_visit_sms" not in {m.get("template_code") for m in row["messages"]}


def test_a_row_with_no_job_type_is_refused_by_name(brazos, marcus):
    """The commit door validates the rows BEFORE its transaction opens
    (`services._field_visit`), exactly as the move-in does."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            customers_services._field_visit({"orders": [{"note": "no type"}]})
        with pytest.raises(errors.ValidationError):
            customers_services._field_visit({"none": True, "orders": [{"type_id": "x"}]})

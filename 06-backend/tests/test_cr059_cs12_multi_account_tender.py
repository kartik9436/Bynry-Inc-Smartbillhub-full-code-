# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-12 (task 49) — *"One payment covering several accounts
#           — the multi-property tender"*. Task 74's fixture scenario is the
#           figures below.
# Story:    US-PAY-001 · US-PAY-006   Screens: S22 · S35 · S21 · S33 · P5
# Rules:    BR-PAY-1126 (one tender may settle several accounts of ONE customer,
#           recorded as one tender row and N payments — never N unrelated
#           payments) · BR-PAY-1127 (the parts must sum to the tender EXACTLY,
#           or the whole submission is refused; nothing partial commits) ·
#           BR-PAY-1128 (each account's payment carries its OWN duplicate-guard
#           key) · BR-CUS-054 (the customer entity) · CLAUDE.md rule 1 · rule 2
#           · rule 4 · rule 5 · rule 6 · rule 7 · law 14
# Tests:    this file
# ───────────────────────────────────────────────────────
"""ONE CHEQUE, THREE PROPERTIES — CR-059 CS-12.

THE FIGURES, WHICH ARE THE CHANGE REQUEST'S OWN AND ALSO TASK 74's FIXTURE
==========================================================================
    cheque #8842, 8 August                                        520.00
      ACC-1042  12 Oak St Unit 1                                  184.20
      ACC-1043  12 Oak St Unit 2                                  156.90
      ACC-1044  40 Cedar Ave                                      178.90
                                                                  ------
                                                                  520.00

Today that is three independent recordings that re-join only at the bank, three
receipts printed for one cheque, and **nothing checks the split**: type
184.20 / 156.90 / **179.90** and the product accepts all three happily.

⚠⚠ THE TRAP, AND IT IS THE REASON THIS FILE EXISTS
===================================================
The duplicate guard is keyed on **tenant + token, NOT on the account**. A form
that minted ONE token and reused it across the three accounts would have
payments two and three treated as replays: the server returns payment one,
**reports success, and writes nothing.**

    in the drawer   520.00
    recorded        184.20
    errors raised   none

THE RED PROOF, RUN BEFORE ANY OF THIS WAS TRUSTED GREEN (hard-won law 7)
=========================================================================
Both guards were broken FIRST, one at a time, through `monkeypatch` — never by
editing a live file, which is `DEF-3101`'s lesson — and the failures are quoted
in the cases below:

  * **Guard 1 off** (`tender_part_reference` patched to ignore the account, i.e.
    the exact one-token version CS-12 warns about): guard 2 fires and the whole
    submission is refused. `test_cs12__the_one_token_version_is_refused_by_name`
    is written to see precisely that.
  * **Guards 1 AND 2 off**: `test_cs12__with_both_guards_off_the_money_
    disappears_silently` records **ONE payment of 184.20 against a cheque of
    520.00, raises nothing**, and the tender row claims 520.00 while holding
    335.80 that was never taken. That case is the defect, pinned, and it is
    marked `xfail(strict=True)` in neither direction — it asserts the BROKEN
    behaviour deliberately so a reader can see what the guards are for.
  * **The sum check off**: `test_cs12__a_split_that_does_not_add_up_is_refused`
    fails with `DID NOT RAISE PaymentRuleError`, and 521.00 of payments are
    written against a 520.00 cheque.

WHAT IS ASSERTED AND NOT REBUILT (CS-12, verbatim)
===================================================
*"three balanced journal entries are not an error (each settled a different
account's receivable)"* — `test_cs12__three_balanced_entries_are_correct` pins
that, so a later lane cannot "tidy" the posting path into one entry and call it
a fix.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import customer_position, models, tender_models, tenders
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill, journal_legs, leg
from tests.test_us_pay_020_023_bank_rec import an_account_of
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

# ── CS-12's own scenario, and CR-059 task 74's fixture ─────────────────────
CHEQUE = Decimal("520.00")
OAK_1 = Decimal("184.20")
OAK_2 = Decimal("156.90")
CEDAR = Decimal("178.90")
#: The typo CS-12 names: *"type 184.20 / 156.90 / 179.90 and the product accepts
#: all three happily."* One dollar over.
CEDAR_TYPO = Decimal("179.90")

CHEQUE_NO = "8842"
PAID_ON = datetime(2026, 8, 8, 10, 0, tzinfo=UTC)
ISSUED_ON = date(2026, 8, 1)


def three_properties_of_one_customer(actor, tenant):
    """*"A customer with three properties"* — one customer, three accounts, one
    open bill each, at CS-12's own figures."""
    from apps.customers import models as customer_models

    accounts = [
        an_account(actor, tenant, account_no="ACC-1042"),
        an_account_of(actor, tenant, service="electric"),
        an_account_of(actor, tenant, service="water"),
    ]
    accounts[1].account_no = "ACC-1043"
    accounts[1].save(update_fields=["account_no"])
    accounts[2].account_no = "ACC-1044"
    accounts[2].save(update_fields=["account_no"])
    customer = customer_models.Customer.objects.create(
        tenant=tenant,
        customer_no=f"C-{uuid.uuid4().hex[:6]}",
        display_name="Oakwood Holdings",
    )
    for account in accounts:
        customer_models.CustomerAccount.objects.create(
            tenant=tenant, customer=customer, account=account
        )
    for account, owed, number in zip(
        accounts,
        (OAK_1, OAK_2, CEDAR),
        ("BL-2608-001042", "BL-2608-001043", "BL-2608-001044"),
        strict=True,
    ):
        an_issued_bill(tenant, account, number=number, total=owed, issued_on=ISSUED_ON)
    return customer, accounts


def the_cheque(actor, accounts, *, amounts=(OAK_1, OAK_2, CEDAR), total=CHEQUE, token=None):
    """CS-12's submission, exactly as `POST /customers/{id}/payments` builds it."""
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


# ══ THE HEADLINE ═══════════════════════════════════════════════════════════


def test_cs12__one_cheque_becomes_one_tender_and_three_payments(brazos, dana):
    """**BR-PAY-1126 — one tender row and N payments, never N unrelated payments.**

    520.00 in the drawer, 520.00 recorded, three properties settled to zero.
    """
    with tenant_ctx(brazos):
        customer, accounts = three_properties_of_one_customer(dana, brazos)
        result = tenders.record_multi_account_payment(
            dana, customer_id=str(customer.id), **the_cheque(dana, accounts)
        )

        assert result.created is True
        assert result.amount == CHEQUE
        assert len(result.parts) == 3
        assert tender_models.PaymentTender.objects.count() == 1

        recorded = models.Payment.objects.filter(tender_id=result.tender_id)
        assert recorded.count() == 3, (
            "BR-PAY-1126: one cheque must produce ONE tender and THREE payments that "
            f"POINT AT IT, got {recorded.count()} linked rows."
        )
        assert sum(p.amount for p in recorded) == CHEQUE
        # One cheque reads as one cheque: every part carries its number, which is
        # also the column bank reconciliation matches on.
        assert {p.confirmation for p in recorded} == {CHEQUE_NO}
        # Three DIFFERENT PMT- numbers — three receipts for three accounts, all
        # naming one cheque. That is the fix for "three receipts printed for one
        # cheque" with nothing tying them together.
        assert len({p.payment_no for p in recorded}) == 3
        assert all(part.applied > 0 for part in result.parts)
        assert all(part.credit_carried == Decimal("0") for part in result.parts)


def test_cs12__three_balanced_entries_are_correct_and_must_not_be_rebuilt(brazos, dana):
    """**CS-12, verbatim: *"three balanced journal entries are not an error (each
    settled a different account's receivable)"* — and *"must not be rebuilt"*.**

    Pinned here so a later lane cannot "tidy" the 🔒 posting path into one entry
    per tender and call it a fix. The DEBITS sum to the cheque and the CREDITS
    sum to the cheque; what the ledger holds is three balanced pairs.
    """
    with tenant_ctx(brazos):
        customer, accounts = three_properties_of_one_customer(dana, brazos)
        tenders.record_multi_account_payment(
            dana, customer_id=str(customer.id), **the_cheque(dana, accounts)
        )
        legs = journal_legs(brazos)
        debits = sum(amount for _, side, amount in legs if side == "debit")
        credits = sum(amount for _, side, amount in legs if side == "credit")
        assert debits == credits == CHEQUE
        # Every tender clears through undeposited funds (OQ-490, PO 2026-08-27),
        # so the day's takings still tie to the drawer as one figure.
        assert leg(legs, "1010", "debit") == CHEQUE


# ══ THE TRAP · BOTH GUARDS, ASSERTED SEPARATELY (DEF-058) ══════════════════


def test_cs12__every_part_carries_its_own_duplicate_guard_key(brazos, dana):
    """**BR-PAY-1128 — guard 1, the design fix, measured on the stored column.**

    Three accounts, three DIFFERENT `webhook_key`s. That column is what
    `uq_payments_webhook_key` is unique on, so three distinct values is the whole
    of why payments two and three are not replays of payment one.
    """
    token = str(uuid.uuid4())
    with tenant_ctx(brazos):
        customer, accounts = three_properties_of_one_customer(dana, brazos)
        result = tenders.record_multi_account_payment(
            dana, customer_id=str(customer.id), **the_cheque(dana, accounts, token=token)
        )
        keys = list(
            models.Payment.objects.filter(tender_id=result.tender_id).values_list(
                "webhook_key", flat=True
            )
        )
    assert len(set(keys)) == 3, f"BR-PAY-1128: one key per ACCOUNT, got {keys}"
    assert all(key.startswith(f"entry|{token}#") for key in keys), (
        "the part key is the submission token PLUS the account, folded through "
        f"`idempotency.inbound_payment_key`. got {keys}"
    )


def test_cs12__the_one_token_version_is_refused_by_name(brazos, dana, monkeypatch):
    """⛔ **GUARD 1 BROKEN — this is the one-token form CS-12 warns about.**

    `tender_part_reference` is patched to IGNORE the account, which is exactly
    what a form minting one token and reusing it would produce. Guard 2 catches
    it: a tender created a microsecond ago cannot own a payment that already
    existed.

    **With guard 2 also removed this case reports SUCCESS over 335.80 that was
    never taken** — see the next test, which pins that behaviour deliberately.
    """
    monkeypatch.setattr(tenders, "tender_part_reference", lambda token, account_id: str(token))
    with tenant_ctx(brazos):
        customer, accounts = three_properties_of_one_customer(dana, brazos)
        with pytest.raises(PaymentRuleError) as caught:
            tenders.record_multi_account_payment(
                dana, customer_id=str(customer.id), **the_cheque(dana, accounts)
            )
        assert "REPLAY" in str(caught.value)
        assert caught.value.br_ref == "BR-PAY-1128"
        # Nothing partial commits — not even the first part, which DID record
        # before the second collided with it.
        assert models.Payment.objects.count() == 0
        assert tender_models.PaymentTender.objects.count() == 0


def test_cs12__with_both_guards_off_the_money_disappears_silently(brazos, dana, monkeypatch):
    """⛔ **THE DEFECT ITSELF, PINNED. This test asserts the BROKEN behaviour.**

    It exists so the two guards can never be quietly removed together and called
    a simplification: with both off, CS-12's worked figure is reproduced exactly
    — **in the drawer 520.00, recorded 184.20, errors raised none.**

    If a later change makes this case fail, that is GOOD news and the case
    should be deleted rather than repaired: it means the failure it describes is
    no longer reachable.
    """
    monkeypatch.setattr(tenders, "tender_part_reference", lambda token, account_id: str(token))
    monkeypatch.setattr(
        tenders,
        "_refuse_a_replay_under_a_new_tender",
        lambda **kwargs: None,
    )
    with tenant_ctx(brazos):
        customer, accounts = three_properties_of_one_customer(dana, brazos)
        result = tenders.record_multi_account_payment(
            dana, customer_id=str(customer.id), **the_cheque(dana, accounts)
        )
        # No exception. A "success".
        assert result.created is True
        assert result.amount == CHEQUE, "the tender claims the whole cheque"
        recorded = models.Payment.objects.all()
        assert recorded.count() == 1, "…and ONE payment exists"
        assert recorded.first().amount == OAK_1
        assert CHEQUE - OAK_1 == Decimal("335.80"), "…so 335.80 was silently not taken"


# ══ BR-PAY-1127 · THE SUM, AND NOTHING PARTIAL ═════════════════════════════


def test_cs12__a_split_that_does_not_add_up_is_refused_whole(brazos, dana):
    """**BR-PAY-1127 — CS-12's own typo: 184.20 / 156.90 / 179.90 against 520.00.**

    Today *"the product accepts all three happily."* Here nothing at all is
    recorded, and the refusal states both figures and the difference, because
    *"the amounts do not add up"* is not something a clerk can act on.
    """
    with tenant_ctx(brazos):
        customer, accounts = three_properties_of_one_customer(dana, brazos)
        with pytest.raises(PaymentRuleError) as caught:
            tenders.record_multi_account_payment(
                dana,
                customer_id=str(customer.id),
                **the_cheque(dana, accounts, amounts=(OAK_1, OAK_2, CEDAR_TYPO)),
            )
        message = str(caught.value)
        assert "521.0000" in message and "520.0000" in message and "1.0000 over" in message
        assert caught.value.br_ref == "BR-PAY-1127"
        # Checked BEFORE the transaction opens, so no PMT- number is burnt and
        # no tender is left behind.
        assert models.Payment.objects.count() == 0
        assert tender_models.PaymentTender.objects.count() == 0


def test_cs12__a_repeated_account_is_refused_because_the_keys_would_collide(brazos, dana):
    """Two rows against ONE account would derive the SAME part key, so the second
    would be stored as a replay of the first — CS-12's trap wearing a different
    hat. Refused by name rather than merged, because merging would silently
    change what the clerk asked for on a money path."""
    with tenant_ctx(brazos):
        customer, accounts = three_properties_of_one_customer(dana, brazos)
        parts = (
            tenders.TenderPart(account_id=accounts[0].pk, amount=Decimal("100.00")),
            tenders.TenderPart(account_id=accounts[0].pk, amount=Decimal("84.20")),
        )
        with pytest.raises(PaymentRuleError) as caught:
            tenders.record_multi_account_payment(
                dana,
                customer_id=str(customer.id),
                parts=parts,
                amount=Decimal("184.20"),
                posted_at=PAID_ON,
                cleared_at=PAID_ON,
                submission_key=str(uuid.uuid4()),
            )
    assert caught.value.br_ref == "BR-PAY-1128"
    assert "twice" in str(caught.value)


# ══ HARD RULE 6 · THE WHOLE SUBMISSION REPLAYS ═════════════════════════════


def test_cs12__a_resubmitted_cheque_records_nothing_a_second_time(brazos, dana):
    """**Hard rule 6 at the SUBMISSION level.** A clerk double-clicks Record;
    one tender, three payments, 520.00 once.

    `created=False` is a RESULT and never an exception — a double-clicked button
    is doing the right thing (the same ruling `POST /accounts/{id}/payments`
    records: 200, not 409)."""
    token = str(uuid.uuid4())
    with tenant_ctx(brazos):
        customer, accounts = three_properties_of_one_customer(dana, brazos)
        first = tenders.record_multi_account_payment(
            dana, customer_id=str(customer.id), **the_cheque(dana, accounts, token=token)
        )
        second = tenders.record_multi_account_payment(
            dana, customer_id=str(customer.id), **the_cheque(dana, accounts, token=token)
        )
        assert first.created is True and second.created is False
        assert second.tender_id == first.tender_id
        assert tender_models.PaymentTender.objects.count() == 1
        assert models.Payment.objects.count() == 3
        assert sum(p.amount for p in models.Payment.objects.all()) == CHEQUE
        assert all(part.created is False for part in second.parts)


# ══ BR-CUS-054 · WHOSE ACCOUNTS ════════════════════════════════════════════


def test_cs12__an_account_the_customer_does_not_hold_is_refused(brazos, dana):
    """*"Several accounts of ONE customer"* — a shared surname or address counts
    for nothing (BR-CUS-054). The stranger's account is named in the refusal, and
    the refusal points at the PREMISES path, which is where a landlord paying
    somebody else's bills belongs."""
    with tenant_ctx(brazos):
        customer, accounts = three_properties_of_one_customer(dana, brazos)
        # Brazos Bend sells Electric and Water and nothing else, so the
        # stranger is on one of those — a unit of a service this tenant does
        # not sell is refused by metering (VAL-005) before the payments rule
        # under test is ever reached.
        stranger = an_account_of(dana, brazos, service="water")
        with pytest.raises(PaymentRuleError) as caught:
            tenders.record_multi_account_payment(
                dana,
                customer_id=str(customer.id),
                parts=(tenders.TenderPart(account_id=stranger.pk, amount=CHEQUE),),
                amount=CHEQUE,
                posted_at=PAID_ON,
                cleared_at=PAID_ON,
                submission_key=str(uuid.uuid4()),
            )
    assert str(stranger.pk) in str(caught.value)
    assert "CS-27" in str(caught.value)
    assert caught.value.br_ref == "BR-PAY-1126"


def test_cs12__naming_both_a_customer_and_a_payer_is_refused(brazos, dana):
    """The two scopes are different keys and different authority questions, so a
    submission that does not say which it is cannot be checked against either."""
    with tenant_ctx(brazos):
        customer, accounts = three_properties_of_one_customer(dana, brazos)
        with pytest.raises(PaymentRuleError) as caught:
            tenders.record_multi_account_payment(
                dana,
                customer_id=str(customer.id),
                payer_account_id=str(accounts[0].pk),
                **the_cheque(dana, accounts),
            )
    assert caught.value.br_ref == "BR-PAY-1126"


# ══ THE LEFTOVER · REPORTED, NEVER REFUSED, ON A CUSTOMER TENDER ═══════════


def test_cs12__an_overpayment_parks_on_one_account_and_says_so(brazos, dana):
    """CS-12: *"Overpay at 600.00 and the 80.00 remainder parks on ONE account
    and auto-applies to that account's next bill, unreachable by a sibling in
    arrears."*

    It is the customer's OWN money on their OWN account, so it is lawful and is
    NOT refused — but the sibling problem is real, so it is stated with its
    figure and CS-8 is named as the door. **This is the opposite of the premises
    path**, where the same leftover is refused because the payer is not the
    holder (BR-PAY-1130).
    """
    with tenant_ctx(brazos):
        customer, accounts = three_properties_of_one_customer(dana, brazos)
        result = tenders.record_multi_account_payment(
            dana,
            customer_id=str(customer.id),
            **the_cheque(
                dana,
                accounts,
                amounts=(OAK_1 + Decimal("80.00"), OAK_2, CEDAR),
                total=CHEQUE + Decimal("80.00"),
            ),
        )
        codes = {problem["code"] for problem in result.problems}
        assert "remainder_parks_on_one_account" in codes
        detail = next(
            p["detail"] for p in result.problems if p["code"] == "remainder_parks_on_one_account"
        )
        assert "80.00" in detail and "CS-8" in detail
        assert result.parts[0].credit_carried == Decimal("80.00")


# ══ THE ROLL-UP READ A CLERK AIMS AT ═══════════════════════════════════════


def test_cs12__the_customer_roll_up_lists_every_property_and_what_it_owes(brazos, dana):
    """The list `GET /customers/{id}/open-bills` serves — three properties,
    520.00 across them, summed over exactly the rows below the header."""
    with tenant_ctx(brazos):
        customer, accounts = three_properties_of_one_customer(dana, brazos)
        body = customer_position.customer_open_bill_position(customer_id=str(customer.id))
    assert body["account_count"] == 3
    assert Decimal(body["total_open"]) == CHEQUE
    assert {row["account_no"] for row in body["accounts"]} == {
        "ACC-1042",
        "ACC-1043",
        "ACC-1044",
    }
    assert {Decimal(row["total_open"]) for row in body["accounts"]} == {OAK_1, OAK_2, CEDAR}
    assert body["customer"]["display_name"] == "Oakwood Holdings"


def test_cs12__the_roll_up_refuses_a_customer_this_tenant_does_not_hold(brazos, dana):
    """CLAUDE.md rule 1. The SAME sentence and rule the record call refuses by,
    so a clerk is never shown a list for a customer the payment bounces off."""
    with tenant_ctx(brazos):
        with pytest.raises(PaymentRuleError) as caught:
            customer_position.customer_open_bill_position(customer_id=str(uuid.uuid4()))
    assert caught.value.br_ref == "BR-CUS-054"


# ══ THE ROUTES RESOLVE (DEF-524: a check pointed at a path that is gone
#    reports PASS through every defect underneath it) ══════════════════════


def test_cs12__the_two_customer_routes_resolve_through_config_urls():
    """Hard-won law 2 with a URL: an endpoint no router mounts is a feature that
    does not exist, and every test that calls the SERVICE would still pass."""
    from django.urls import resolve

    from apps.payments import tenders_api

    assert resolve("/api/v1/customers/abc/payments").func is tenders_api.customer_payments
    assert resolve("/api/v1/customers/abc/open-bills").func is tenders_api.customer_open_bills


# ══ LAW 14 · THE ONE GUARANTEE SQLITE CANNOT TEST ═════════════════════════


@pytest.mark.isolation
def test_cs12__all_or_nothing_holds_on_a_real_database(brazos, dana, monkeypatch):
    """**BR-PAY-1127 — a refusal on the LAST part unwinds the first two.**

    ⚠ **This is the case CLAUDE.md law 14 is about.** The default suite runs on
    in-memory SQLite (`config/settings/test.py` hardcodes it and ignores
    `DATABASE_URL`), and SQLite has no aborted-transaction state — so a rollback
    that is broken on PostgreSQL passes here. It was run against a live
    PostgreSQL 16 cluster before being trusted; the assertion is the same on
    both and the MEANING is not.

    The third part is made to refuse from inside the transaction, after two
    payments, two allocations, two journal entries and their audit rows have
    already been written.
    """
    calls = {"n": 0}
    real = tenders.record_payment

    def refuse_the_third(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise PaymentRuleError("the third part is refused", br_ref="BR-PAY-1127")
        return real(*args, **kwargs)

    monkeypatch.setattr(tenders, "record_payment", refuse_the_third)
    with tenant_ctx(brazos):
        customer, accounts = three_properties_of_one_customer(dana, brazos)
        with pytest.raises(PaymentRuleError):
            tenders.record_multi_account_payment(
                dana, customer_id=str(customer.id), **the_cheque(dana, accounts)
            )
        assert models.Payment.objects.count() == 0, (
            "BR-PAY-1127: nothing partial commits. Two payments had already been written "
            "when the third refused, and the transaction must take them with it."
        )
        assert tender_models.PaymentTender.objects.count() == 0
        assert journal_legs(brazos) == []

# ── Trace ──────────────────────────────────────────────
# Rules:   BR-CUS-1030 (a transfer REASSIGNS the account — one account, never
#          closed, the CUSTOMER changes) · BR-CWP-029 (a password attaches to a
#          person ALREADY ON FILE) · CLAUDE.md hard rule 1 (tenant scoping) ·
#          hard-won law 7 (prove a guard goes RED before trusting it green)
# Change:  `customers/0060` made a property sale END the seller's
#          `customer_accounts` row instead of DELETING it, so a sold account
#          now holds TWO rows. Its own review-ledger entry reported that about
#          forty readers of that table had never been asked whether they want
#          the LIVE link, and named `apps/portal/credentials.py` as the one
#          that matters most.
# Tests:   this file — the three sign-in-path readers
# ───────────────────────────────────────────────────────
"""**A PERSON WHO SOLD A PROPERTY MUST NOT REACH ITS PORTAL.**

⚠ **THIS IS THE COST OF `customers/0060` AND IT IS BEING PAID DELIBERATELY.**
Before that migration a sale DELETED the seller's link, so every reader of
`customer_accounts` got the current customer by construction and none of them
had to say so. Ending the row instead keeps *who sold this property* — which is
what the PO ruled on 2026-09-20 — and hands every one of those readers a second
row they were never written to expect.

**`credentials.py` is the reader where that costs the most**, because its three
link reads decide **who may sign in to an account**:

  * `find_account` matches a typed NAME against the account's customer, and is
    the door onto enrolment;
  * `already_enrolled` decides whether the visitor is routed to *reset your
    password*;
  * `create_credential` **attaches the new password to `link.customer_id`.**

⛔ **SO AN UNFILTERED READ IS NOT A TIDINESS PROBLEM HERE. IT IS EITHER THE
SELLER KEEPING A DOOR INTO A HOUSE THEY SOLD, OR THE BUYER'S OWN PASSWORD BEING
FILED AGAINST THE SELLER.** Which of the two happens depends on nothing more
than which row the database hands back first, because none of the three orders
its query — so it is not even reliably one of them.

⚠ **`CustomerAccount.objects` IS DELIBERATELY UNFILTERED** (see the model's own
note): a manager that hid ended rows would also have hidden them from the
property-sale suite, whose whole point is to prove the seller SURVIVES. So the
duty is on each caller to say `live()` when it means *now*, and these three
mean *now*.

**THE FIXTURE IS A SALE, NOT A HAND-BUILT PAIR OF ROWS.** It ends the seller's
link exactly as `reassign_account` does — `ended_at` set, `ended_by_transfer_id`
set, the row left in place — because a test that invents its own shape for the
state it is guarding proves only that the shape it invented behaves.
"""

from __future__ import annotations

import uuid

import pytest

from apps.customers import models as customers_models
from apps.portal import credentials
from apps.portal import models as portal_models
from core.tenancy import tenant_context
from django.utils import timezone

from tests.test_us_cwp_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_cwp_helpers import elm_street_account

pytestmark = pytest.mark.django_db

SELLER_TYPED = "Maria Alvarez"
BUYER_NAME = "Okonjo, Nadia"


def _sell_the_property(tenant, account):
    """End the seller's link and give the buyer a live one — as a sale does.

    Returns `(seller, buyer)`. The seller's row is **left in place** with
    `ended_at` written, which is the whole state this file exists to guard.
    """
    with tenant_context(tenant.id):
        seller_link = (
            customers_models.CustomerAccount.objects.filter(
                tenant_id=tenant.id, account_id=account.pk
            )
            .select_related("customer")
            .first()
        )
        assert seller_link is not None, "the fixture account must start with a customer"
        seller = seller_link.customer

        buyer = customers_models.Customer.objects.create(
            tenant_id=tenant.id,
            display_name=BUYER_NAME,
            kind=seller.kind,
        )
        customers_models.CustomerAccount.objects.create(
            tenant_id=tenant.id, customer_id=buyer.id, account_id=account.pk
        )
        # Exactly what `transfers.reassign_account` writes.
        customers_models.CustomerAccount.objects.filter(pk=seller_link.pk).update(
            ended_at=timezone.now(), ended_by_transfer_id=uuid.uuid4()
        )
    return seller, buyer


def _postcode_of(tenant, account):
    from apps.metering import models as metering_models

    with tenant_context(tenant.id):
        premises_id = account.premises_id or getattr(account.unit, "premises_id", None)
        row = metering_models.Premises.objects.filter(
            tenant_id=tenant.id, pk=premises_id
        ).only("postal_code").first()
        return str(getattr(row, "postal_code", "") or "")


def test_def_cus_6048__the_seller_cannot_enrol_on_a_property_they_sold(pine_hill, sarah):
    """⛔ The door onto enrolment must not open to the previous owner.

    `find_account` is what turns *account number + postcode + name* into an
    account to enrol against. Handed the SELLER's name after the sale it must
    answer None — the same answer a stranger gets, and for the same reason.
    """
    account = elm_street_account(pine_hill, sarah)
    seller, _buyer = _sell_the_property(pine_hill, account)
    postcode = _postcode_of(pine_hill, account)

    with tenant_context(pine_hill.id):
        found = credentials.find_account(
            pine_hill.id,
            account_no=account.account_no,
            postcode=postcode,
            name=seller.display_name,
        )

    assert found is None, (
        "the person who SOLD this property was offered enrolment on it — "
        "their `customer_accounts` row is ended, and this read did not ask"
    )


def test_def_cus_6048__the_buyer_can_enrol_on_the_property_they_bought(pine_hill, sarah):
    """The mirror, and it is not optional.

    ⚠ **A read that answered None to everybody would pass the case above and be
    useless**, so the same fixture is asked the opposite question. This is
    hard-won law 7's second habit — what would make the guard above pass
    WRONGLY — written as a case rather than as a comment.
    """
    account = elm_street_account(pine_hill, sarah)
    _seller, buyer = _sell_the_property(pine_hill, account)
    postcode = _postcode_of(pine_hill, account)

    with tenant_context(pine_hill.id):
        found = credentials.find_account(
            pine_hill.id,
            account_no=account.account_no,
            postcode=postcode,
            name=buyer.display_name,
        )

    assert found is not None, "the BUYER was refused enrolment on the property they now own"
    assert str(found.pk) == str(account.pk)


def test_def_cus_6048__a_new_password_attaches_to_the_buyer_and_never_the_seller(
    pine_hill, sarah
):
    """⛔ **THE WORST OF THE THREE.**

    `create_credential` files the password against `link.customer_id`. With the
    seller's ended row still readable, the buyer's own password can be attached
    to the person who sold them the house — who could then sign in with it.
    """
    account = elm_street_account(pine_hill, sarah)
    seller, buyer = _sell_the_property(pine_hill, account)

    with tenant_context(pine_hill.id):
        credential = credentials.create_credential(
            pine_hill.id,
            account=account,
            email="nadia.okonjo@example.test",
            password="Sh0rtleaf-Pine-2026",
            otp_channel=portal_models.CHANNEL_SMS,
        )

    assert str(credential.customer_id) == str(buyer.id), (
        "the buyer's password was filed against the wrong person"
    )
    assert str(credential.customer_id) != str(seller.id), (
        "the buyer's password was attached to the SELLER — who can now sign in "
        "to a property they no longer own"
    )


def test_def_cus_6048__already_enrolled_reads_the_buyers_login_not_the_sellers(
    pine_hill, sarah
):
    """A seller's old login must not make the buyer look already enrolled.

    The visitor is routed to *reset your password* on a true answer here, so a
    stale one sends the new owner down a path that can only end at the previous
    owner's credential.
    """
    account = elm_street_account(pine_hill, sarah)
    seller, _buyer = _sell_the_property(pine_hill, account)

    with tenant_context(pine_hill.id):
        # The SELLER holds a login, from before the sale. The BUYER does not.
        portal_models.PortalCredential.objects.create(
            tenant_id=pine_hill.id,
            customer_id=seller.id,
            email="maria.alvarez@example.test",
            password_hash="!",
            password_changed_on=timezone.now(),
            otp_channel=portal_models.CHANNEL_SMS,
            status=portal_models.CREDENTIAL_ACTIVE,
        )
        answer = credentials.already_enrolled(pine_hill.id, account)

    assert answer is False, (
        "the SELLER's login was read as this account's — the buyer would be sent "
        "to reset a password that is not theirs"
    )

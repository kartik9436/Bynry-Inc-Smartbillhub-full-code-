# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-049 (EP-CWP-09) — refunds returned to the method the money
#           came in on. Screen: CWP-045 (the refund half)
# Rules:    BR-CWP-060 (a refund returns to the method the money came in on and
#           the timeline NAMES it) · BR-PAY-014 (check/ACH in v1 — a CARD
#           refund waits for rails W7; `card` is not a value `refunds.method`
#           can hold) · BR-CWP-010 · CLAUDE.md hard rule 2 · hard rule 4
# Cases:    TC-1 card in · TC-2 cheque in, with the address · ⚠ TC-3 the expired
#           card · TC-4 two methods · TC-5 the voided refund · TC-6 isolation ·
#           TC-7 the four steps
# ───────────────────────────────────────────────────────
"""**THE TIMELINE MAY NOT SAY *to the card ending 8812* TODAY, AND SAYING IT
WOULD BE A LIE ON A CUSTOMER'S SCREEN.**

`US-CWP-049` TC-1 draws exactly that sentence. `BR-PAY-014` — CONFIRMED, and
the constraint `ck_refunds_method` enforces it in the database — puts card
refunds behind the payment rails (W7): `REFUND_METHODS` is `("check", "ach")`
and there is no third value. So a refund of money that came in by card goes out
by **cheque or ACH today**, whatever the drawn copy says.

**Printing *to the card ending 8812* over a cheque that is in the post is
hard-won law 1 pointed at a customer** — a sentence claiming a guarantee the
code does not make. What ships instead is the SAME fact told truthfully: the
screen names **where the money came in**, names **where it is going**, and when
those differ it says WHY. `TC-3` is the story's own version of exactly that
shape (*"falls back to a cheque and the timeline says so — never silently to a
dead card"*), so the fallback is signed behaviour rather than a lane's
invention; what this lane found is that it is the ONLY shape available today.

⚠ **AND A DEAD CARD OUTRANKS ABSENT RAILS IN THE SENTENCE.** Both are true of an
expired card, and only one of them is still true the day rails land. The reason
the customer is given is the one that will not evaporate.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.payments import models as payments_models, refunds, services
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import elm_street_account

#: `US-CWP-049` §4 — the story's own figures.
THE_REFUND = Decimal("89.80")
RAISED_AT = datetime(2026, 9, 18, 9, 0, tzinfo=UTC)
APPROVED_AT = datetime(2026, 9, 19, 9, 0, tzinfo=UTC)
ISSUED_AT = datetime(2026, 9, 21, 9, 0, tzinfo=UTC)
PAID_AT = datetime(2026, 6, 13, 9, 0, tzinfo=UTC)
CHEQUE_NO = "10241"


def _overpayment(actor, account, *, method_code, amount=Decimal("120.00")):
    """One cleared payment that meets no bill, so all of it becomes credit."""
    with tenant_context(account.tenant_id):
        return services.record_payment(
            actor,
            account_id=account.pk,
            amount=amount,
            posted_at=PAID_AT,
            cleared_at=PAID_AT,
            method_code=method_code,
            idempotency_reference=uuid.uuid4(),
        )


def _a_customer_holding(tenant, account):
    """The customer THIS ACCOUNT ALREADY BELONGS TO.

    ⚠ **READ, NOT CREATED, AND THE FIRST DRAFT GOT THIS WRONG IN A WAY WORTH
    KEEPING.** `BR-CUS-054` makes the link a TABLE (`customer_accounts`) because
    a landlord holds many accounts — so a fixture that MINTS a customer and
    links it gets a SECOND holder, while `customer_for_account` keeps returning
    the seeded first one by `created_at`. The card then hangs off a customer the
    product never looks at, and the screen shows no card at all with every row
    present in the database. That is the shape of the whole story: a digit on a
    customer's screen must come off the row the product actually reads.
    """
    from apps.customers import models as customers_models
    from apps.customers import selectors as customers_selectors

    with tenant_context(tenant.id):
        held = customers_selectors.customer_for_account(account.pk)
        if held is not None:
            return customers_models.Customer.objects.get(pk=held["id"])
        customer = customers_models.Customer.objects.create(
            tenant=tenant, display_name="Maria Alvarez"
        )
        customers_models.CustomerAccount.objects.create(
            tenant=tenant, customer=customer, account=account
        )
        return customer


def _a_mailing_address(tenant, account):
    """Where the post goes — `customers.addresses kind='mailing'`, CLAUDE.md
    hard rule 8's first exception (*where the BILL goes*)."""
    from apps.customers import models as customers_models

    with tenant_context(tenant.id):
        return customers_models.Address.objects.create(
            tenant=tenant,
            account=account,
            kind="mailing",
            line1="91 Cedar Row",
            city="Austin",
            state="TX",
            postal_code="78704",
        )


def _a_saved_card(tenant, account, *, last_four="8812", brand="Visa", status=None):
    """A card the customer saved. ⚠ Written through the model rather than a
    service because `apps/payments/instruments.py` belongs to another lane —
    this fixture asserts nothing about how the row is CREATED."""
    customer = _a_customer_holding(tenant, account)
    with tenant_context(tenant.id):
        return payments_models.StoredPaymentInstrument.objects.create(
            tenant=tenant,
            customer=customer,
            gateway_token=f"tok_{uuid.uuid4().hex}",
            brand=brand,
            last_four=last_four,
            kind=payments_models.INSTRUMENT_CARD,
            status=status or payments_models.INSTRUMENT_ACTIVE,
            expires_month=11,
            expires_year=2029,
        )


def _refund_of(actor, account, *, payment=None, method, reference=None):
    with tenant_context(account.tenant_id):
        raised = refunds.request_refund(
            actor,
            payment_id=payment.payment_id if payment is not None else None,
            account_id=None if payment is not None else account.pk,
            amount=THE_REFUND,
            method=method,
            reference=reference,
            requested_at=RAISED_AT,
            idempotency_key=str(uuid.uuid4()),
        )
        refunds.approve_refund(actor, refund_id=raised.refund_id, approved_at=APPROVED_AT)
        refunds.issue_refund(actor, refund_id=raised.refund_id, issued_at=ISSUED_AT)
        return payments_models.Refund.objects.get(pk=raised.refund_id)


def _destination(tenant, refund):
    with tenant_context(tenant.id):
        return refunds.destination_of(refund)


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 · MONEY CAME IN BY CARD
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc1_card_in_names_the_card_and_states_where_it_actually_went(pine_hill, sarah):
    """The screen names the card the money came in on **and** the cheque it is
    going back on, because those are two different facts and both are true."""
    account = elm_street_account(pine_hill, sarah)
    _a_saved_card(pine_hill, account)
    paid = _overpayment(sarah, account, method_code="card")
    refund = _refund_of(
        sarah,
        account,
        payment=paid,
        method=payments_models.REFUND_METHOD_CHECK,
        reference=CHEQUE_NO,
    )

    where = _destination(pine_hill, refund)

    assert where["came_in_by"] == "card"
    assert where["brand"] == "Visa"
    assert where["last_four"] == "8812"
    # ⚠ NOT `original_method`: `REFUND_METHODS` has no `card` (BR-PAY-014).
    assert where["kind"] == refunds.DESTINATION_FALLBACK
    assert where["fallback_reason"] == refunds.FALLBACK_CARD_RAILS_ABSENT
    assert where["method"] == payments_models.REFUND_METHOD_CHECK
    assert where["reference"] == CHEQUE_NO


@pytest.mark.django_db
def test_tc1_the_card_fallback_expires_when_refunds_can_name_a_card(pine_hill, sarah):
    """⚠ **THE FALLBACK'S OWN EXPIRY TEST** (hard-won law 2's mirror).

    `FALLBACK_CARD_RAILS_ABSENT` is true only while `refunds.method` cannot hold
    `card`. The day it can, the sentence *we sent a cheque instead* has stopped
    being true and this goes RED naming the screen — rather than a customer
    reading it over a card refund that worked.
    """
    assert payments_models.REFUND_METHODS == ("check", "ach"), (
        "refunds can name a card now: CWP-045's fallback sentence "
        "(refunds.FALLBACK_CARD_RAILS_ABSENT and its catalogue line) must be "
        "released in the same commit"
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 · MONEY CAME IN BY CHEQUE
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc2_cheque_in_cheque_out_is_the_original_method(pine_hill, sarah):
    """`#10241`, and no fallback sentence — the money is going back the way it
    came, which is what `BR-CWP-060` asks for."""
    account = elm_street_account(pine_hill, sarah)
    paid = _overpayment(sarah, account, method_code="check")
    refund = _refund_of(
        sarah,
        account,
        payment=paid,
        method=payments_models.REFUND_METHOD_CHECK,
        reference=CHEQUE_NO,
    )

    where = _destination(pine_hill, refund)

    assert where["kind"] == refunds.DESTINATION_ORIGINAL
    assert where["came_in_by"] == "check"
    assert where["reference"] == CHEQUE_NO
    assert where["fallback_reason"] is None


@pytest.mark.django_db
def test_tc2_the_address_it_went_to_is_the_mailing_address(pine_hill, sarah):
    """⚠ **THE ADDRESS IS `customers.addresses kind='mailing'` AND IS ADDED BY
    THE PORTAL SEAM, NOT BY `payments`** (CLAUDE.md hard rule 8's first
    exception — *where the BILL goes*, which for a landlord is another
    building). A cheque goes where the post goes.
    """
    from apps.portal.seams import payments_seam

    account = elm_street_account(pine_hill, sarah)
    _a_mailing_address(pine_hill, account)
    paid = _overpayment(sarah, account, method_code="check")
    _refund_of(
        sarah,
        account,
        payment=paid,
        method=payments_models.REFUND_METHOD_CHECK,
        reference=CHEQUE_NO,
    )

    with tenant_context(pine_hill.id):
        rows = payments_seam.refunds_for(account.pk)

    assert len(rows) == 1
    where = rows[0]["destination"]
    assert where["kind"] == refunds.DESTINATION_ORIGINAL
    # `US-CWP-049` §4's own envelope: `91 Cedar Row, Austin TX 78704`.
    assert where["posted_to"] == "91 Cedar Row, Austin, TX 78704"


# ═══════════════════════════════════════════════════════════════════════════
# ⚠ TC-3 · THE EXPIRED CARD
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc3_an_expired_card_falls_back_and_the_timeline_says_which_reason(pine_hill, sarah):
    """⚠ **NEVER SILENTLY TO A DEAD CARD.**

    Both reasons are true — the card is expired AND no card rails exist — and
    the one the customer is told is the one that survives the day rails land.
    """
    account = elm_street_account(pine_hill, sarah)
    _a_saved_card(
        pine_hill,
        account,
        last_four="4417",
        status=payments_models.INSTRUMENT_EXPIRED,
    )
    paid = _overpayment(sarah, account, method_code="card")
    refund = _refund_of(
        sarah,
        account,
        payment=paid,
        method=payments_models.REFUND_METHOD_CHECK,
        reference=CHEQUE_NO,
    )

    where = _destination(pine_hill, refund)

    assert where["kind"] == refunds.DESTINATION_FALLBACK
    assert where["fallback_reason"] == refunds.FALLBACK_CARD_EXPIRED
    assert where["last_four"] == "4417"
    assert where["method"] == payments_models.REFUND_METHOD_CHECK


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 · MONEY CAME IN ACROSS TWO METHODS
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc4_two_methods_names_the_rule_that_chose_one_and_never_a_bare_sent(pine_hill, sarah):
    """⚠ **NEVER A BARE *sent*.**

    A refund built from several payments carries `payment_id: None` (`OQ-195`,
    PO 2026-09-01), so no single payment describes where the money came in. The
    destination says exactly that, by name, rather than picking one of the two.
    """
    account = elm_street_account(pine_hill, sarah)
    _overpayment(sarah, account, method_code="card", amount=Decimal("60.00"))
    _overpayment(sarah, account, method_code="check", amount=Decimal("60.00"))
    refund = _refund_of(
        sarah,
        account,
        payment=None,
        method=payments_models.REFUND_METHOD_CHECK,
        reference=CHEQUE_NO,
    )

    where = _destination(pine_hill, refund)

    assert where["kind"] == refunds.DESTINATION_FALLBACK
    assert where["fallback_reason"] == refunds.FALLBACK_SEVERAL_SOURCES
    assert where["came_in_by"] is None
    # It still says where the money IS going — the bare *sent* is what TC-4 bans.
    assert where["method"] == payments_models.REFUND_METHOD_CHECK


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 · A VOIDED REFUND
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc5_a_voided_refund_keeps_its_destination_and_is_not_removed(pine_hill, sarah):
    """A customer told money was coming and then shown nothing has no way to ask
    what happened to it (`US-CWP-056` TC-4, restated here for the refund half)."""
    from apps.portal.seams import payments_seam

    account = elm_street_account(pine_hill, sarah)
    paid = _overpayment(sarah, account, method_code="check")
    refund = _refund_of(
        sarah,
        account,
        payment=paid,
        method=payments_models.REFUND_METHOD_CHECK,
        reference=CHEQUE_NO,
    )
    with tenant_context(pine_hill.id):
        refunds.void_refund(
            sarah,
            refund_id=str(refund.pk),
            void_reason="cheque lost in the post",
            voided_at=ISSUED_AT,
        )
        rows = payments_seam.refunds_for(account.pk)

    assert len(rows) == 1
    assert rows[0]["voided_at"] is not None
    assert rows[0]["destination"]["kind"] == refunds.DESTINATION_ORIGINAL
    # ⚠ The utility's own note stays the utility's (BR-CWP-051's posture).
    assert "void_reason" not in rows[0]


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 · TENANT ISOLATION
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc6_a_pine_hill_session_sees_pine_hill_refunds_only(pine_hill, sarah, oak_ridge, elena):
    """⚠ **ASKED OF THE WRONG TENANT, WITH THE RIGHT ACCOUNT ID.**

    `BR-CWP-010` lives in the QUERY, so the way to prove it is to run the read
    under Oak Ridge's context naming a Pine Hill account and watch it come back
    empty — `US-CWP-012` TC-5's shape. A test that built two tenants' rows and
    read one would pass over a read that filtered in Python instead of in SQL.
    """
    del elena  # the Oak Ridge tenant is the fixture; no actor of theirs is needed
    from apps.portal.seams import payments_seam

    account = elm_street_account(pine_hill, sarah)
    paid = _overpayment(sarah, account, method_code="check")
    _refund_of(
        sarah,
        account,
        payment=paid,
        method=payments_models.REFUND_METHOD_CHECK,
        reference=CHEQUE_NO,
    )

    with tenant_context(pine_hill.id):
        mine = payments_seam.refunds_for(account.pk)
    with tenant_context(oak_ridge.id):
        theirs = payments_seam.refunds_for(account.pk)

    assert [row["reference"] for row in mine] == [CHEQUE_NO]
    assert theirs == [], "an Oak Ridge session read a Pine Hill refund by naming its account id"


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 · THE FOUR LIFECYCLE STEPS
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc7_four_steps_and_the_one_that_has_not_happened_carries_no_date(pine_hill, sarah):
    from apps.portal.seams import payments_seam

    account = elm_street_account(pine_hill, sarah)
    paid = _overpayment(sarah, account, method_code="check")
    _refund_of(
        sarah,
        account,
        payment=paid,
        method=payments_models.REFUND_METHOD_CHECK,
        reference=CHEQUE_NO,
    )

    with tenant_context(pine_hill.id):
        row = payments_seam.refunds_for(account.pk)[0]

    assert [step["step"] for step in row["steps"]] == [
        "requested",
        "approved",
        "issued",
        "cleared",
    ]
    assert row["steps"][3]["on"] is None, "cleared has not happened and invents no date"

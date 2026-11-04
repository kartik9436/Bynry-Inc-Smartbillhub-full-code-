# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-004 (EP-CWP-02) — check and pay, and the masked name that
#           makes it safe. Screens: CWP-003 · wireframes/CWP-003.png
# Rules:    BR-CWP-019 (the amount owing and a MASKED name and NOTHING ELSE) ·
#           BR-CWP-020 (`M. A••••••`, masked SERVER-SIDE) · BR-CWP-021 (a guest
#           sees an amount and a status, never a person) · BR-CWP-023 (five
#           wrong pairs, fifteen minutes — and step 2 is the SAME door) ·
#           BR-CWP-026 (no guest write changes an account) · BR-CWP-056 (a
#           control that cannot be used is disabled with its reason) ·
#           BR-CWP-057 (a stored instrument is a token, a brand and a last
#           four) · BR-CWP-058 (the screen shows where the payment lands before
#           it commits) · CLAUDE.md hard rule 2 (four stored, two displayed) ·
#           hard rule 6 (idempotency) · hard rule 7 (every money action writes
#           audit_log — a guest payment still names WHO)
# Tests:    this file — TC-1 (the masked name and nothing else IN THE PAYLOAD) ·
#           TC-3 (a forced commit against a bill nobody may pay writes nothing)
#           · TC-4 (a one-letter surname masks to a FIXED width) · TC-5 (tenant
#           isolation, refused before a customer row is read) · TC-6 (the
#           charge carries the re-read figure, the guest channel and a WHO) ·
#           TC-7 (a gateway that does not answer writes no payment row)
# Impacts:  apps/portal/guest_api.bill_pay · selectors.guest_payment_receipt ·
#           guest_fields.py
# ───────────────────────────────────────────────────────
"""What a stranger may be told at the moment they pay, and what the edge
refuses to do on their behalf.

⚠ **THE DISCLOSURE CASE ASSERTS OVER THE PAYLOAD, NOT OVER THE DOM.** `US-CWP-004`
§5 is verbatim about it — *"Masked server-side. Never send the full name and
mask in the browser"* — so a test that renders a screen and fails to find
*Maria Alvarez* proves nothing at all: the browser would already have been told.
Every disclosure case here reads `response.data` and freezes the whole key set.

⚠ **AND STEP 2 IS THE SAME DOOR AS STEP 1, WHICH IS THE POINT OF `_pay` NOT
TAKING A TOKEN FROM STEP 1.** `US-CWP-002`'s five-tries lockout guards
`bills/lookup`; a commit endpoint that trusted a client-held "I already looked
this up" would be a second door onto the same secret with no counter on it. So
the pair is re-proved here, a miss burns a try, and the refusal is the one
sentence step 1 gives.
"""

from __future__ import annotations

import sys
import types
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.portal import guest_api, lockout, selectors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_024_balance import allocate
from tests.test_us_cwp_helpers import (
    an_issued_bill,
    elm_street_account,
    switch_on,
)
from tests.test_us_ten_helpers import api_call

#: `US-CWP-004` §4, verbatim.
AUGUST = date(2026, 8, 30)
DUE = date(2026, 9, 14)
BILL = "BL-2608-0141"
POSTCODE = "78702"
WRONG_POSTCODE = "78704"
OWING = "142.1800"
DISPLAY = "$142.18"
MASKED = "M. A••••••"
REFERENCE = "PAY-26-08841"
RECEIPT_EMAIL = "d.okafor@example.com"

GUESSER = "198.51.100.10"
SECOND_ADDRESS = "203.0.113.7"

#: `BR-CWP-057` — a token, a brand and a last four. ⚠ **NO CARD NUMBER APPEARS
#: ANYWHERE IN THIS FILE**, which is `US-CWP-004` §5's *"Never stored"* asserted
#: by the shape of the fixture rather than by a sentence about it.
INSTRUMENT = {"token": "tok_sandbox_8812", "brand": "visa", "last_four": "8812"}


class _Gateway:
    """A stand-in for lane B's `apps/payments/gateway.py`, RECORDING.

    ⚠ **IT IS A RECORDER AND NOT A MOCK LIBRARY** for the reason
    `QuickPay.dom.test.tsx` records one directory over: what these cases assert
    is *what the edge handed the rails*, and the argument list is the contract.
    """

    def __init__(self, *, raises: Exception | None = None):
        self.calls: list[dict] = []
        self.raises = raises

    def charge_guest_bill(self, tenant_id, **kwargs):
        self.calls.append({"tenant_id": tenant_id, **kwargs})
        if self.raises is not None:
            raise self.raises
        return {
            "reference": REFERENCE,
            "amount": Decimal(kwargs["amount"]),
            "currency": kwargs["currency"],
            "paid_at": datetime(2026, 9, 2, 9, 47, tzinfo=UTC),
            "method_brand": INSTRUMENT["brand"],
            "method_last_four": INSTRUMENT["last_four"],
            "receipt_sent": kwargs.get("receipt_email") is not None,
        }


@pytest.fixture
def rails(monkeypatch):
    """Install the recorder where `bill_pay` looks for the rails.

    ⚠ **`apps.payments.gateway` DOES NOT EXIST ON THIS BRANCH YET** — it is
    lane B's, built in parallel — so the module is SYNTHESISED here rather than
    patched onto a real one. The day it lands, this fixture keeps working and
    the edge's contract is what it still asserts; delete it and the edge is
    exercised against the real rails.
    """
    gateway = _Gateway()
    module = types.ModuleType("apps.payments.gateway")
    module.charge_guest_bill = gateway.charge_guest_bill  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "apps.payments.gateway", module)
    return gateway


def _pay(tenant, number, body, address=SECOND_ADDRESS):
    return api_call(
        guest_api.bill_pay,
        "post",
        f"/api/{tenant.subdomain}/portal/public/bills/{number}/pay",
        tenant=tenant,
        data=body,
        headers={"X-Forwarded-For": address},
        number=number,
    )


def _good_body(**overrides):
    body = {
        "postcode": POSTCODE,
        "amount": OWING,
        "instrument": dict(INSTRUMENT),
        "receipt_email": None,
        "attempt_token": "5f8c0f1e-0000-4000-8000-0000000008841",
    }
    body.update(overrides)
    return body


def _elm_bill(tenant, actor, *, number=BILL, total=OWING, status=billing_models.INVOICE_ISSUED):
    """One bill on Maria's `1408 Elm St · A`, whose premises postcode is 78702."""
    switch_on(tenant, actor)
    account = elm_street_account(tenant, actor)
    with tenant_context(tenant.id):
        row = an_issued_bill(
            tenant, account, number=number, total=total, issued_on=AUGUST, due_on=DUE
        )
        if status != billing_models.INVOICE_ISSUED:
            row.status = status
            row.save(update_fields=["status"])
    return account, row


# ══ TC-1 — the masked name, in the PAYLOAD, and nothing else ═══════════════


@pytest.mark.django_db
def test_tc1_step_two_is_told_a_masked_name_and_never_the_customer(pine_hill, sarah):
    """`US-CWP-004` TC-1 — *the response body contains no other field of the
    customer record*.

    ⚠ **THIS ASSERTS THE WIRE, NOT THE SCREEN.** The check-and-pay screen loads
    its facts from `bills/lookup`, so that is the payload the rule bites on, and
    the case freezes the WHOLE key set: a field a future serialiser gains goes
    red here, including the one nobody thought of.
    """
    _elm_bill(pine_hill, sarah)
    response = api_call(
        guest_api.bill_lookup,
        "post",
        f"/api/{pine_hill.subdomain}/portal/public/bills/lookup",
        tenant=pine_hill,
        data={"bill_number": BILL, "postcode": POSTCODE},
        headers={"X-Forwarded-For": SECOND_ADDRESS},
    )
    assert response.status_code == 200
    body = dict(response.data)
    assert body["masked_name"] == MASKED
    assert set(body) == {"number", "amount", "status", "due_on", "masked_name", "replaced_by"}
    assert "Maria" not in str(body)
    assert "Alvarez" not in str(body)


# ══ TC-4 — a one-letter surname masks to a FIXED width ═════════════════════


def test_tc4_the_mask_is_fixed_width_and_does_not_count_the_letters():
    """`US-CWP-004` TC-4 — *"M. O"* masks *without revealing length*.

    A mask of one dot per letter would turn the screen into a length oracle:
    *O••* and *A••••••* are two different surnames before anybody types
    anything. The mask is a CONSTANT, so `O` and `Alvarez` are indistinguishable.
    """
    short = selectors.masked_name("Marcus O")
    long = selectors.masked_name("Maria Alvarez")
    assert short == "M. O••••••"
    assert len(short) == len(long)


# ══ TC-6 — the charge carries the RE-READ figure, the channel and a WHO ════


@pytest.mark.django_db
def test_tc6_the_edge_charges_the_reread_figure_and_names_who_paid(pine_hill, sarah, rails):
    """`US-CWP-004` §7 — *the amount owing at the moment of commit, re-read
    rather than carried from step 1* — and hard rule 7's WHO.

    ⚠ **A GUEST PAYMENT STILL NAMES SOMEBODY.** There is no user, so the actor
    is the CHANNEL and a constant that says *this came off the public form*.
    A money action with no actor is a row nobody can explain a year later.
    """
    _elm_bill(pine_hill, sarah)
    response = _pay(pine_hill, BILL, _good_body(receipt_email=RECEIPT_EMAIL))

    assert response.status_code == 201, response.data
    assert len(rails.calls) == 1
    call = rails.calls[0]
    assert call["bill_number"] == BILL
    assert Decimal(call["amount"]) == Decimal(OWING)
    assert call["channel"] == "customer_portal"
    assert call["paid_by"] == guest_api.GUEST_PAID_BY
    # ⚠ **THIS READ `== RECEIPT_EMAIL` UNTIL `DEF-CWP-3951`, AND IT IS THE
    # DEFECT'S OWN ESCAPE REASON STANDING IN A TEST FILE.** The case asserted
    # that the address the caller typed reached the rails — which was TRUE —
    # and nothing anywhere asked what became of it after that. Nothing sent to
    # it: `record_payment` queues a receipt to the ACCOUNT's own contacts, a
    # different address, and `BR-NOT-013` means nothing dispatches at all. A
    # form that collects something the product never reads is indistinguishable,
    # to every check in this repo, from one that acts on it.
    #
    # The edge now passes `None` and the form no longer asks. The PARAMETER
    # stays on the rails — it is the door the address goes through the day
    # dispatch arrives — and the expiry alarm is
    # `tests/test_def_cwp_3951_the_receipt_address_goes_nowhere.py`.
    assert call["receipt_email"] is None
    # Hard rule 6 — the same attempt twice must be harmless, so a key travels.
    assert call["idempotency_key"]
    # `BR-CWP-057` — a token and its two visible facts. Never a card number.
    assert set(call["instrument"]) == {"token", "brand", "last_four"}


@pytest.mark.django_db
def test_tc6_the_receipt_carries_a_reference_and_no_person(pine_hill, sarah, rails):
    """The answer is `BR-CWP-028`'s reference and `BR-CWP-021`'s nothing-else."""
    _elm_bill(pine_hill, sarah)
    body = dict(_pay(pine_hill, BILL, _good_body()).data)

    assert body["reference"] == REFERENCE
    assert body["against"] == BILL
    assert body["amount"]["display"] == DISPLAY
    assert body["amount"]["amount"] == OWING
    assert set(body) == {"reference", "amount", "paid_at", "against", "method", "receipt_sent"}
    assert set(body["method"]) == {"brand", "last_four"}
    assert "Maria" not in str(body) and "Alvarez" not in str(body)
    # ⚠ NO EMAIL COMES BACK, EVEN THE ONE THAT WAS SENT IN. A neighbour may
    # legitimately type their own address at step 2 (`US-CWP-004` §4); echoing
    # it would put an address on a screen anybody holding the bill can reach.
    assert RECEIPT_EMAIL not in str(body)


# ══ TC-3 — a forced commit writes nothing ══════════════════════════════════


@pytest.mark.django_db
def test_tc3_a_settled_bill_cannot_be_paid_and_the_rails_are_never_reached(pine_hill, sarah, rails):
    """`US-CWP-004` TC-3 — *no payment row, no audit row, no gateway call*.

    The screen disables the control on a settled bill; this is the same refusal
    at the EDGE, because `BR-CWP-002`'s posture is that a screen which merely
    does not draw a door is defeated by calling the door directly.
    """
    account, bill = _elm_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        #: ⚠ **A REAL ALLOCATION, NOT A FLIPPED STATUS COLUMN** — the reasoning
        #: `test_us_cwp_003_bill_lookup.py` TC-4 records: the word this screen
        #: shows is derived from what `payments` says is still open, so a fixture
        #: that only edited `invoices.status` would prove the assertion and not
        #: the behaviour.
        allocate(pine_hill, account, bill, OWING)
        bill.status = billing_models.INVOICE_PAID
        bill.save(update_fields=["status"])

    response = _pay(pine_hill, BILL, _good_body())
    assert response.status_code == 409
    assert rails.calls == []


@pytest.mark.django_db
def test_tc3_a_figure_that_moved_between_the_two_steps_is_refused(pine_hill, sarah, rails):
    """`BR-CWP-058` — *the screen shows where the payment will land before it
    commits*, so a figure that moved under the person is not quietly charged.

    ⚠ **IT REFUSES RATHER THAN CHARGING THE NEW NUMBER.** Somebody who agreed
    to `$142.18` did not agree to `$182.18`; hard rule 4 makes a payment row a
    thing that can only be reversed, never corrected, so the cheap moment to be
    careful is before it exists.
    """
    _elm_bill(pine_hill, sarah)
    response = _pay(pine_hill, BILL, _good_body(amount="100.0000"))
    assert response.status_code == 409
    assert rails.calls == []


# ══ TC-5 — tenant isolation, refused before a customer row is read ═════════


@pytest.mark.django_db
def test_tc5_another_utilitys_bill_number_is_refused_under_this_tenant(
    pine_hill, oak_ridge, sarah, elena, rails
):
    """`US-CWP-004` TC-5 — Pine Hill's number posted at Oak Ridge is refused."""
    _elm_bill(pine_hill, sarah)
    switch_on(oak_ridge, elena)

    response = _pay(oak_ridge, BILL, _good_body())
    assert response.status_code == 409
    assert rails.calls == []


# ══ US-CWP-002 — step 2 is the SAME door, and the lockout holds it ═════════


@pytest.mark.django_db
def test_the_five_tries_lockout_cannot_be_walked_round_by_starting_at_step_two(
    pine_hill, sarah, rails
):
    """`BR-CWP-023` — five wrong pairs lock the form, and **the commit endpoint
    is the same form**.

    ⚠ **THE ATTACK THIS CLOSES IS THE ONLY REASON THE PAIR IS RE-PROVED HERE.**
    `bills/lookup` counts wrong pairs; if the commit trusted a client-held
    "I already looked this up", a guesser would simply stop calling step 1.
    """
    _elm_bill(pine_hill, sarah)
    for _ in range(5):
        assert (
            _pay(pine_hill, BILL, _good_body(postcode=WRONG_POSTCODE), GUESSER).status_code == 409
        )

    # The SIXTH attempt is locked — and a CORRECT pair inside the window is
    # refused too, which is what makes it a lockout rather than a delay.
    locked = _pay(pine_hill, BILL, _good_body(), GUESSER)
    assert locked.status_code == 409
    assert lockout.is_locked(str(pine_hill.id), lockout.FORM_QUICK_PAY, GUESSER)
    assert rails.calls == []


@pytest.mark.django_db
def test_a_wrong_pair_at_step_two_refuses_exactly_as_step_one_does(pine_hill, sarah, rails):
    """The two refusals are the SAME sentence — *"a different message would
    confirm the bill number exists"* (`US-CWP-003` TC-2), and a commit endpoint
    that said *"wrong postcode"* would undo that in one line."""
    _elm_bill(pine_hill, sarah)
    at_step_one = api_call(
        guest_api.bill_lookup,
        "post",
        f"/api/{pine_hill.subdomain}/portal/public/bills/lookup",
        tenant=pine_hill,
        data={"bill_number": BILL, "postcode": WRONG_POSTCODE},
        headers={"X-Forwarded-For": SECOND_ADDRESS},
    )
    at_step_two = _pay(pine_hill, BILL, _good_body(postcode=WRONG_POSTCODE))

    def without_trace(response):
        return {k: v for k, v in dict(response.data).items() if k != "trace_id"}

    assert without_trace(at_step_two) == without_trace(at_step_one)
    assert rails.calls == []


# ══ TC-7 — an unknown outcome writes nothing ═══════════════════════════════


@pytest.mark.django_db
def test_tc7_a_gateway_that_does_not_answer_leaves_no_payment_row(pine_hill, sarah, monkeypatch):
    """`US-CWP-004` TC-7 — *no payment row is written on an unknown outcome; a
    zero is a claim nobody can make*.

    The edge does not catch this and invent a state: the failure travels, and
    the SCREEN says so. What is asserted is that nothing here converts *"we do
    not know"* into a receipt.
    """
    _elm_bill(pine_hill, sarah)
    gateway = _Gateway(raises=TimeoutError("the acquirer did not answer"))
    module = types.ModuleType("apps.payments.gateway")
    module.charge_guest_bill = gateway.charge_guest_bill  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "apps.payments.gateway", module)

    response = _pay(pine_hill, BILL, _good_body())
    assert response.status_code == 503
    assert "reference" not in dict(response.data)


# ══ BR-CWP-002 — a utility that switched quick pay off refuses the ENDPOINT ═


@pytest.mark.django_db
def test_a_utility_with_quick_pay_switched_off_refuses_the_commit_too(pine_hill, sarah, rails):
    """`BR-CWP-002` — the refusal is at the edge, not at the screen."""
    _elm_bill(pine_hill, sarah)
    switch_on(pine_hill, sarah, quick_pay_enabled=False)

    response = _pay(pine_hill, BILL, _good_body())
    assert response.status_code == 409
    assert rails.calls == []


# ══ BR-CWP-057 — nothing here will accept a card number ════════════════════


@pytest.mark.django_db
def test_a_body_carrying_a_card_number_is_refused_by_name(pine_hill, sarah, rails):
    """`US-CWP-004` §5 — the card number is posted to the GATEWAY and never to
    us: *"Never stored."*

    ⚠ **REFUSED RATHER THAN DROPPED**, the posture `POST /public/reports` takes
    for an attached photo one file over. A field quietly ignored is a field a
    future serialiser starts logging.
    """
    _elm_bill(pine_hill, sarah)
    for forbidden in ("card_number", "pan", "cvc", "security_code", "expiry"):
        body = _good_body()
        body[forbidden] = "4111111111111111"
        assert _pay(pine_hill, BILL, body).status_code == 409, forbidden
    assert rails.calls == []

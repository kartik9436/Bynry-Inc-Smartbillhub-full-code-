# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-005 (EP-CWP-02) — paid: a reference to keep, and the offer of
#           a login. Screens: CWP-004 · wireframes/CWP-004.png
# Rules:    BR-CWP-028 (every guest flow ends on a reference, offers to send it,
#           and can be looked up with it) · BR-CWP-029 (enrolment attaches a
#           password to a person already on file) · BR-CWP-021 (a guest sees an
#           amount and a status, never a person) · B14 rule 31 (the reference is
#           the HUMAN one — `PAY-26-08841`, never a row id) · CLAUDE.md hard
#           rule 2 (four stored, two displayed) · hard rule 4 (a payment row is
#           reversed, never edited)
# Tests:    this file — TC-1 (the reference, the amount, the bill, the method) ·
#           TC-3 (no credential row is created by paying) · the receipt view
#           carries no uuid and no person · **TC-3's other half, added
#           2026-09-05**: the receipt is reachable by its reference after a
#           reload, and what comes back carries the status and the two dates
#           and NOT the amount (US-CWP-010 TC-7) · TC-5 (the same reference
#           under another utility is not found)
# Impacts:  apps/portal/selectors.guest_payment_receipt · selectors.track ·
#           selectors.payment_progress_view · seams/payments_seam.
#           payment_by_number · guest_api.bill_pay · guest_fields.py
# ───────────────────────────────────────────────────────
"""The end of the guest journey: what a person is given to keep.

⚠ **THE OFFER OF A LOGIN IS UNCONDITIONAL, AND THAT IS A DISCLOSURE DECISION
RATHER THAN A LAZY ONE.** `US-CWP-005` §1 wants the offer made at *"the single
best moment in the product"*. A server flag saying *this account has no login
yet* would answer a question a neighbour holding the bill has no business
asking, so the offer is always drawn and `/enrol` protects itself — `TC-4`
requires exactly that: taking the offer *does not skip the one-time code
because a payment just succeeded*.
"""

from __future__ import annotations

import sys
import types
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.portal import guest_api, selectors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    an_issued_bill,
    elm_street_account,
    switch_on,
)
from tests.test_us_ten_helpers import api_call

#: `US-CWP-005` §4, verbatim.
AUGUST = date(2026, 8, 30)
DUE = date(2026, 9, 14)
BILL = "BL-2608-0141"
POSTCODE = "78702"
OWING = "142.1800"
DISPLAY = "$142.18"
REFERENCE = "PAY-26-08841"
PAID_AT = datetime(2026, 9, 2, 9, 47, tzinfo=UTC)
BRAND = "visa"
LAST_FOUR = "8812"

ADDRESS = "203.0.113.7"


@pytest.fixture
def rails(monkeypatch):
    """Lane B's `apps/payments/gateway.py`, synthesised — see
    `test_us_cwp_004_pay.py` for why it is a module rather than a patch."""
    calls: list[dict] = []

    def charge_guest_bill(tenant_id, **kwargs):
        calls.append({"tenant_id": tenant_id, **kwargs})
        return {
            "reference": REFERENCE,
            "amount": Decimal(kwargs["amount"]),
            "currency": kwargs["currency"],
            "paid_at": PAID_AT,
            "method_brand": BRAND,
            "method_last_four": LAST_FOUR,
            "receipt_sent": kwargs.get("receipt_email") is not None,
        }

    module = types.ModuleType("apps.payments.gateway")
    module.charge_guest_bill = charge_guest_bill  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "apps.payments.gateway", module)
    return calls


def _paid(tenant, actor, *, receipt_email=None):
    switch_on(tenant, actor)
    account = elm_street_account(tenant, actor)
    with tenant_context(tenant.id):
        an_issued_bill(tenant, account, number=BILL, total=OWING, issued_on=AUGUST, due_on=DUE)
    return api_call(
        guest_api.bill_pay,
        "post",
        f"/api/{tenant.subdomain}/portal/public/bills/{BILL}/pay",
        tenant=tenant,
        data={
            "postcode": POSTCODE,
            "amount": OWING,
            "instrument": {"token": "tok_sandbox_8812", "brand": BRAND, "last_four": LAST_FOUR},
            "receipt_email": receipt_email,
            "attempt_token": "5f8c0f1e-0000-4000-8000-0000000008841",
        },
        headers={"X-Forwarded-For": ADDRESS},
        number=BILL,
    )


# ══ TC-1 — the reference, the amount, the bill and the method ══════════════


@pytest.mark.django_db
def test_tc1_a_completed_guest_payment_answers_a_reference_to_keep(pine_hill, sarah, rails):
    """`US-CWP-005` TC-1 — `PAY-26-08841` on screen, with the amount, the bill
    and the method."""
    body = dict(_paid(pine_hill, sarah).data)

    assert body["reference"] == REFERENCE
    assert body["amount"]["display"] == DISPLAY
    assert body["against"] == BILL
    assert body["method"] == {"brand": BRAND, "last_four": LAST_FOUR}
    assert body["paid_at"] == PAID_AT.isoformat()


@pytest.mark.django_db
def test_the_receipt_names_no_row_id_anywhere(pine_hill, sarah, rails):
    """B14 rule 31 — *no database id is ever the visible value of a field*, and
    `BR-CWP-021` is stricter still: a guest sees no internals at all.

    ⚠ **ASSERTED BY SHAPE RATHER THAN BY EYE.** Every value is checked for the
    32-hex-and-dashes look of a uuid, so a future field carrying one goes red
    without anybody remembering to add a case for it.
    """
    import re

    body = dict(_paid(pine_hill, sarah).data)
    uuid_like = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
    assert not uuid_like.search(str(body)), body


# ══ TC-2 — the receipt is not withheld for want of an email ════════════════


@pytest.mark.django_db
def test_tc2_paying_without_an_email_still_answers_the_reference(pine_hill, sarah, rails):
    """`US-CWP-005` TC-2 — *the receipt is already downloadable without it*.

    Nothing here makes the reference conditional on an address, which is the
    half of TC-2 the server owns; the prompt is the screen's.
    """
    body = dict(_paid(pine_hill, sarah, receipt_email=None).data)
    assert body["reference"] == REFERENCE
    assert body["receipt_sent"] is False


@pytest.mark.django_db
def test_an_email_given_at_step_two_is_reported_as_a_fact_and_never_echoed(pine_hill, sarah, rails):
    """A neighbour may legitimately type their own address (`US-CWP-004` §4), so
    what comes back is *whether* it was sent — never *where*."""
    body = dict(_paid(pine_hill, sarah, receipt_email="d.okafor@example.com").data)
    assert body["receipt_sent"] is True
    assert "okafor" not in str(body).lower()


# ══ TC-3 — paying creates no login ═════════════════════════════════════════


@pytest.mark.django_db
def test_tc3_paying_as_a_guest_creates_no_credential_row(pine_hill, sarah, rails):
    """`US-CWP-005` TC-3 — *no credential row was created*, and `BR-CWP-026`:
    no guest write changes an account.

    ⚠ **COUNTED BEFORE AND AFTER RATHER THAN ASSERTED ONCE.** A count of zero
    proves nothing on a tenant that never had one; the delta is the claim.
    """
    from apps.portal import models as portal_models

    switch_on(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        before = portal_models.PortalCredential.objects.count()

    _paid(pine_hill, sarah)

    with tenant_context(pine_hill.id):
        assert portal_models.PortalCredential.objects.count() == before


# ══ The view builder itself, `guest_fields.py`'s allow-list made real ══════


def test_the_receipt_view_carries_exactly_the_declared_keys():
    """`G92` reads `selectors.guest_payment_receipt` statically; this asserts the
    same list on a value the function actually returns, which is the half a
    static read cannot do."""
    view = selectors.guest_payment_receipt(
        {
            "reference": REFERENCE,
            "amount": Decimal(OWING),
            "currency": "USD",
            "paid_at": PAID_AT,
            "method_brand": BRAND,
            "method_last_four": LAST_FOUR,
            "receipt_sent": False,
        },
        bill_number=BILL,
    )
    assert set(view) == {"reference", "amount", "paid_at", "against", "method", "receipt_sent"}
    assert view["amount"]["amount"] == OWING
    assert view["amount"]["display"] == DISPLAY


# ══ TC-3, the OTHER half — *the receipt is still reachable by reference* ═══
#
# ⚠ **TWO SIGNED STATEMENTS MEET HERE AND NEITHER HAD TO MOVE.**
# `US-CWP-005` TC-3 says *"the receipt is still reachable by reference"* and
# `US-CWP-010` TC-7 says a tracked payment answers *"its status and date. ⚠
# **Not the amount** — the amount is account data."* Read together they are
# `BR-CWP-028` promising the LOOKUP and `BR-CWP-024` bounding what the lookup
# RETURNS. So a person who reloads `/pay/done` can find their payment again —
# and what they find carries no money at all. The cases below assert BOTH
# halves, because a lane reading only the first would widen the payload and a
# lane reading only the second would never build the door.
#
# ⚠ **THE PAYMENT ROW IS WRITTEN DIRECTLY AND THAT IS A CONSTRAINT, NOT A
# SHORTCUT.** `gateway.charge_guest_bill` does not exist yet — `apps/payments/
# gateway.py` says so in its own docstring, at length, and the `rails` fixture
# above synthesises it for exactly that reason. What is under test here is the
# LOOKUP, not the write; the day the rails land, the `rails` fixture is what
# changes and not these assertions.

PAID_POSTED = datetime(2026, 9, 2, 9, 47, tzinfo=UTC)
CLEARED = datetime(2026, 9, 3, 6, 15, tzinfo=UTC)


def _a_recorded_payment(tenant, account, *, reference=REFERENCE, status="cleared", cleared=CLEARED):
    """One `payments.Payment` on Maria's account, numbered `PAY-26-08841`."""
    from apps.payments import models as payments_models

    with tenant_context(tenant.id):
        return payments_models.Payment.objects.create(
            tenant=tenant,
            account=account,
            payment_no=reference,
            type=payments_models.PAYMENT_TYPE_PAYMENT,
            amount=Decimal(OWING),
            currency="USD",
            status=status,
            posted_at=PAID_POSTED,
            cleared_at=cleared,
        )


def _track(tenant, reference, second_fact, address=ADDRESS):
    return api_call(
        guest_api.track,
        "post",
        f"/api/{tenant.subdomain}/portal/public/track",
        tenant=tenant,
        data={"reference": reference, "second_fact": second_fact},
        headers={"X-Forwarded-For": address},
    )


@pytest.mark.django_db
def test_tc3_the_reference_still_finds_the_payment_after_the_tab_is_reloaded(pine_hill, sarah):
    """`US-CWP-005` TC-3 — *the receipt is still reachable by reference*, and
    `US-CWP-010` TC-7 — `PAY-26-08841` + `78702`.

    `/pay/done` carries nothing in its address on purpose, so a refreshed tab
    has lost the receipt. This is the way back, and it needs no login: the
    reference the person kept plus the postcode that was already printed on the
    bill they paid.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _a_recorded_payment(pine_hill, account)

    body = _track(pine_hill, REFERENCE, POSTCODE).data

    assert body["series"] == "payment"
    assert body["reference"] == REFERENCE
    # `DEF-CWP-10341` — a customer's word for money taken, cleared or not.
    assert body["status"] == "received"
    assert body["reported_at"] == PAID_POSTED.isoformat()
    assert body["cleared_at"] == CLEARED.isoformat()


@pytest.mark.django_db
def test_the_tracked_payment_carries_exactly_five_keys_and_not_one_more(pine_hill, sarah):
    """`BR-CWP-024` frozen as a SET, which is the assertion `G92` cannot make.

    ⚠ **THE WHOLE KEY SET, NEVER A LIST OF THINGS THAT ARE ABSENT.** *"A field
    that is served and merely not drawn is still served"* — so the case that
    protects this payload is the one that goes red when a key ARRIVES, not one
    that names the four or five somebody thought of. `masked_name`, `amount`,
    `against` and `method` are all on the receipt and none of them is here.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _a_recorded_payment(pine_hill, account)

    body = dict(_track(pine_hill, REFERENCE, POSTCODE).data)

    assert set(body) == {"series", "reference", "status", "reported_at", "cleared_at"}


@pytest.mark.django_db
def test_tc7_the_tracked_payment_names_no_figure_no_person_and_no_row_id(pine_hill, sarah):
    """`US-CWP-010` TC-7, verbatim: *"⚠ **Not the amount** — the amount is
    account data."* Plus `BR-CWP-021` (never a person) and B14 rule 31 (never a
    row id).

    ⚠ **ASSERTED ON THE WHOLE BODY BY SHAPE**, the way the receipt's own uuid
    case is: a future field carrying a figure or an id goes red here without
    anybody remembering to add a case for it.

    ⚠ **AND THE FOUND SHAPE IS ASSERTED FIRST, WHICH IS NOT DECORATION.**
    Without it this case passes on the REFUSAL body — which contains no figure
    either — so it would be green on a branch where the lookup does not exist
    at all. A check that cannot fail is worse than no check, because it is
    trusted (hard-won law 11's own words about `--stat`).
    """
    import re

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _a_recorded_payment(pine_hill, account)

    found = dict(_track(pine_hill, REFERENCE, POSTCODE).data)
    assert found.get("series") == "payment", found
    body = str(found)

    assert "142" not in body, "TC-7 — the amount is account data"
    assert "$" not in body
    assert not re.search(r"alvarez|maria", body, re.I)
    assert not re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", body, re.I
    )
    # The postcode was typed IN; echoing it back would put the service address
    # on a public response (`NEVER_ON_A_GUEST_RESPONSE` names `postal_code`).
    assert POSTCODE not in body


@pytest.mark.django_db
def test_the_wrong_postcode_is_refused_identically_to_an_unknown_reference(pine_hill, sarah):
    """`US-CWP-010` TC-3 for the new series. A real reference with the wrong
    second fact and a reference nobody ever issued must be **byte-identical** to
    a caller — a different answer for the first would confirm the payment
    exists, which is the enumeration this endpoint is guarded against.

    ⚠ **`trace_id` IS DROPPED BEFORE THE COMPARISON AND IT IS THE ONLY THING
    DROPPED.** It is a fresh id per REQUEST, so two calls can never carry the
    same one and *"byte-identical"* has to mean *"identical but for the thing
    that identifies the call"*. Written out rather than left as a `!=` somebody
    later widens: every other key — `code`, `message_key`, `params`,
    `field_errors`, `br_ref` — must match exactly, and `params` matching is the
    one that matters most, because a refusal that echoed the reference back
    would confirm it exists in the very message that claims not to know it.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _a_recorded_payment(pine_hill, account)

    wrong = _track(pine_hill, REFERENCE, "78704", address="203.0.113.21")
    unknown = _track(pine_hill, "PAY-26-00000", POSTCODE, address="203.0.113.22")

    def without_trace(response):
        return {key: value for key, value in dict(response.data).items() if key != "trace_id"}

    assert wrong.status_code == unknown.status_code
    assert without_trace(wrong) == without_trace(unknown)
    assert wrong.data["message_key"] == "portal.track.notFound"
    assert REFERENCE not in str(without_trace(wrong))


@pytest.mark.django_db
def test_tc5_the_same_reference_under_another_utility_is_not_found(
    pine_hill, sarah, oak_ridge, elena
):
    """`US-CWP-005` TC-5 — *Look up `PAY-26-08841` under `/oak-ridge`: not
    found*, and `US-CWP-010` TC-6 says the same of every series.

    ⚠ **THE TENANT IS IN THE QUERY AND THIS IS WHAT ASSERTS IT** (`G96`). RLS
    `FORCE` would refuse the cross-tenant read a second time in production, and
    the suite runs on SQLite, which has no row-level security at all — so a read
    that leaned on the database would pass every test in this repository forever
    (hard-won law 14 in its second costume).

    ⚠ **THE PAIR IS PROVED TO WORK ON PINE HILL FIRST.** An isolation case that
    only asserts *not found* is green on a branch where NOTHING is found, which
    is a check that cannot fail. The first assertion is what gives the second
    one its meaning.
    """
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    account = elm_street_account(pine_hill, sarah)
    _a_recorded_payment(pine_hill, account)

    assert _track(pine_hill, REFERENCE, POSTCODE).data["series"] == "payment"

    response = _track(oak_ridge, REFERENCE, POSTCODE)

    assert response.status_code in (409, 422)
    assert response.data["message_key"] == "portal.track.notFound"


@pytest.mark.django_db
def test_a_processing_payment_reads_processing_and_offers_no_clearing_date(pine_hill, sarah):
    """`BR-PAY-021` — the two dates always travel, and the second is genuinely
    absent while the money has not arrived. An absence is rendered as an
    absence, never as a zero or as today (`BR-CWP-092`'s reading, applied
    here)."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _a_recorded_payment(pine_hill, account, status="processing", cleared=None)

    body = _track(pine_hill, REFERENCE, POSTCODE).data

    assert body["status"] == "processing"
    assert body["cleared_at"] is None


def test_the_two_ledger_words_never_reach_a_public_page():
    """Six states go in and four words come out (three before `DEF-CWP-10341`).

    *Posted* is a bookkeeping fact and *reversed* names a mechanism — a
    chargeback, a staff correction, a bounced cheque — and `BR-CWP-024` gives a
    guest PROGRESS AND NEVER THE REASON. `report_progress_status` folds
    `refused` into *resolved* on exactly that reading.
    """
    # ⚠ Amended 2026-10-21 (`DEF-CWP-10341`): `posted` and `cleared` both read
    # *received* — bank reconciliation is not the payer's question — and
    # `cancelled` has its own word. The full table is asserted in
    # `test_def_cwp_10341_portal_payment_words.py`.
    assert selectors.payment_progress_status("posted") == "received"
    assert selectors.payment_progress_status("reversed") == "failed"
    assert selectors.payment_progress_status("failed") == "failed"
    assert selectors.payment_progress_status("cleared") == "received"
    # The fallback claims nothing — never a borrowed real word.
    assert selectors.payment_progress_status("something_new") == "unknown"
    assert set(selectors.PAYMENT_PROGRESS_WORDS.values()) == {
        "received", "failed", "processing", "cancelled",
    }


@pytest.mark.django_db
def test_a_credit_or_an_adjustment_is_not_trackable_even_with_the_right_postcode(pine_hill, sarah):
    """The boundary is NARROWER than the story asks and never wider.

    `payments` keeps credits and adjustments in the same table under the same
    numbering, and nothing in this product hands a stranger the number of one.
    A reference that names one is refused identically to an unknown one.

    ⚠ **A REAL PAYMENT ON THE SAME ACCOUNT IS PROVED FINDABLE FIRST**, so this
    case cannot pass merely because nothing is findable — the difference it
    asserts is the TYPE and nothing else.
    """
    from apps.payments import models as payments_models

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _a_recorded_payment(pine_hill, account)
    assert _track(pine_hill, REFERENCE, POSTCODE).data["series"] == "payment"

    with tenant_context(pine_hill.id):
        payments_models.Payment.objects.create(
            tenant=pine_hill,
            account=account,
            payment_no="PAY-26-09001",
            type=payments_models.PAYMENT_TYPE_ADJUSTMENT,
            amount=Decimal("10.0000"),
            currency="USD",
            status="cleared",
            posted_at=PAID_POSTED,
        )

    response = _track(pine_hill, "PAY-26-09001", POSTCODE)
    assert response.data["message_key"] == "portal.track.notFound"


def test_the_series_a_visitor_may_type_now_names_the_payment():
    """`TRACKABLE_SERIES` is the tuple `US-CWP-010`'s TC-7 case reads, and the
    hold that kept `PAY-` out of it has expired.

    It said *"`PAY-` IS DELIBERATELY ABSENT AND THIS IS A WAVE ORDER, NOT A
    GAP"* because the postcode walk did not exist here. `bill_lookup` has taken
    exactly that walk since wave P, so the reason is spent and the tuple moved.
    """
    assert selectors.TRACKABLE_SERIES == ("request", "payment")

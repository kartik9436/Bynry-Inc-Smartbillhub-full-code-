# ── Trace ──────────────────────────────────────────────
# Story:  The Invoice Cloud *Make Payment* API — decision log 2026-09-24,
#         *"THE INVOICE CLOUD *MAKE PAYMENT* API, CONFIRMED BEFORE A LINE IS
#         WRITTEN"*. `POST /api/partner/v1/make-payment/`, the FIRST write on
#         a door whose other eight addresses are reads.
# Rules:  BR-INT-083 (the partner door's one write) · BR-PAY-1197 (an Invoice
#         Cloud payment carries no till) · BR-PAY-1150 (a partner may not
#         waive our late fee) · BR-INT-044 (one refusal, one body, one set of
#         bytes, one time) · BR-PAY-003 / BR-PAY-028 (inbound payment
#         idempotency) · BR-TEN-081 / OQ-153 (a typed date is midnight in the
#         UTILITY's own zone) · CLAUDE.md hard rule 1 · 2 · 4 · 6 · 7 ·
#         hard-won law 7 (name the false pass first, and prove the guard RED)
# ───────────────────────────────────────────────────────
"""A PARTNER CAN NOW CREATE MONEY, AND EVERY GUARD AROUND THAT IS ASSERTED HERE.

WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first, per law 7
--------------------------------------------------------------------
**1 · The duplicate.** Posting twice and asserting one payment exists passes
just as happily with the pre-check DELETED, because `uq_payments_webhook_key`
catches it one layer down — which is exactly how `DEF-058` came to ship a
switched-off hard-rule-6 guard for a day with a green suite. So the two layers
are asserted SEPARATELY: this file asserts the cheap path (no second row, no
second audit row, `duplicate: true`, the ORIGINAL number returned), and
`test_invoice_cloud_make_payment_pg.py` asserts the index by committing the
first copy from a second connection so the pre-check cannot see it. **That race
cannot be shown on SQLite at all** (law 14).

**2 · The refusal indistinguishability.** `assert response.status_code == 404`
proves nothing — an address that does not exist is also a 404. The case walks
the SIX door refusals plus the missing write scope at THIS address and compares
the **whole body byte for byte**, the status, and the time against
`REFUSAL_FLOOR_S`. It reuses `_six_refusals` from the read suite rather than
writing a looser copy, so the two surfaces can never be proved over different
sets.

**3 · The read-only key.** Asserting that a key WITH the write scope succeeds
says nothing about one without it. The case is the negative: the same partner,
the same body, a key scoped to the reads → the stranger's bytes, and **no
payment row anywhere in the tenant**.

**4 · `counter_session_id` being NULL.** It is NULL by default, so `is None`
passes on a build that never looked at tills. Since `CR-186-BRC10` (PO
2026-10-21) the payment DOES carry a deposit batch — the day's Invoice Cloud
batch, stamped at posting — so the case asserts the till is NULL, the batch is
NOT, and the reply names the batch the row carries.

**5 · The hand-tender refusal.** A case that sends `card` and passes says
nothing about `cash`. The case sends `cash` and asserts the refusal BY CODE and
that nothing was written.

**6 · The date.** `2026-06-20` is a valid ISO date and so is a mis-read
`20-06-2026` if a reader is sloppy. The case asserts the STORED instant is
20 June at midnight IN THE TENANT'S ZONE, which is the only assertion that can
tell a correct read from `DEF-094`'s off-by-one-day.

PROVED RED FIRST, in `pytest` — the harness that runs it (`DEF-GOV-3733`).
Each proof is quoted in the lane report with the guard that was broken.
"""

from __future__ import annotations

import json
import time
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.integrations import invoice_cloud_payment as ic
from apps.integrations import models, partner_api, services
from apps.integrations.registry import REGISTRY
from apps.integrations.runners import serve
from core import crypto

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_int_041_partner_surface import (  # the read suite's own fixtures
    ALLOWED_ADDRESS,
    BLOCKED_ADDRESS,
    ALLOWLIST,
    _bytes,
    _six_refusals,
)

#: The connector this address belongs to. ⚠ **NOT `erp_workday`**, which the
#: read suite uses: `record_payment` is declared by exactly one manifest, and
#: a key on any of the five ERPs cannot reach this address at all — which is a
#: property this file asserts rather than assumes.
PARTNER = "pay_invoicecloud_partner"

KEY = "sbh_live_9X4M_brazosbend_make_payment"
HINT = "••••9X4M"

ACCOUNT_NO = "A-10650"
BILL_NO = "INV-2026-00412"
REFERENCE = "TID161007"
#: `DD-MM-YYYY`, their document's spelling. 20 June 2026.
PAID_ON = "20-06-2026"
AMOUNT = "142.18"


def _write_scope() -> list[str]:
    """Every operation this manifest declares — DERIVED, never typed.

    The read suite's `_full_scope` records why at length: a hand-written copy
    went stale inside one day and took nineteen cases with it. The same applies
    here with one extra edge — this list is what makes the write reachable, so
    a typo would refuse every case in this file with the door's five words and
    look exactly like a broken door.
    """
    return [one.name for one in REGISTRY.require(PARTNER).operations if one.they_call_us]


def _read_scope() -> list[str]:
    """The four reads and the document — **a key exactly as they were issued
    before this address existed.** This is the fixture the negative case turns
    on, and deriving it by SUBTRACTION rather than listing it means a sixth
    read operation lands in it automatically and a second WRITE never does."""
    return [one for one in _write_scope() if one != "record_payment"]


def _connect(tenant, actor, *, key=KEY, hint=HINT, scope=None, allowlist=ALLOWLIST):
    """An Invoice Cloud connection with a key we issued.

    Written through `services.record_credential` — the SAME call the issue
    endpoint uses — with the blind index computed from
    `serve.ISSUED_KEY_BLIND_INDEX_CONTEXT`. That constant is imported rather
    than retyped: if the door and the issuer ever hash under different
    contexts, every valid key is refused and the door still looks like it
    works, because a refused key is what a wrong key looks like.
    """
    connection = models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=PARTNER,
        label="InvoiceCloud",
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_WORKING,
        enabled=True,
        cadence=models.CADENCE_MANUAL,
        config={serve.ALLOWLIST_CONFIG_KEY: allowlist},
    )
    services.record_credential(
        actor=actor,
        connection=connection,
        payload=key,
        masked_hint=hint,
        blind_index=crypto.blind_index(key, context=serve.ISSUED_KEY_BLIND_INDEX_CONTEXT),
        scope=list(_write_scope() if scope is None else scope),
    )
    return connection


def _body(**overrides):
    """Their document's body, with only the keys the decision log quotes."""
    body = {
        ic.FIELD_ACCOUNT: ACCOUNT_NO,
        ic.FIELD_BILL: BILL_NO,
        ic.FIELD_REFERENCE: REFERENCE,
        ic.FIELD_DATE: PAID_ON,
        ic.FIELD_AMOUNT: AMOUNT,
        ic.FIELD_CURRENCY: "USD",
        ic.FIELD_METHOD: "card",
        # Accepted, ignored, recorded — PO 2026-09-17.
        ic.FIELD_COMPANY: "393",
        ic.FIELD_TENANT: "302",
    }
    body.update(overrides)
    return {name: value for name, value in body.items() if value is not None}


def _post(tenant, *, key=KEY, address=ALLOWED_ADDRESS, body=None):
    """One partner POST: no session, a bearer key, and a source address.

    `REMOTE_ADDR` rather than `X-Forwarded-For`, for the read suite's own
    reason: with `TRUSTED_PROXY_COUNT = 0` the forwarded header is ignored,
    which is the property that stops a caller spoofing past the allowlist, and
    a test using the header would exercise a path production does not take.
    """
    from rest_framework.test import APIRequestFactory

    from core import tenancy as core_tenancy

    factory = APIRequestFactory()
    request = factory.post(
        "/api/partner/v1/make-payment/",
        data=json.dumps(_body() if body is None else body),
        content_type="application/json",
        REMOTE_ADDR=address,
    )
    if key is not None:
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {key}"
    request.tenant_id = tenant.id
    with core_tenancy.tenant_context(tenant.id):
        return partner_api.partner_make_payment(request)


def _account(tenant, actor, *, account_no=ACCOUNT_NO, service="water"):
    """One account to hang the bill and the money on.

    ⚠ `service` is WATER because Lone Star Ridge sells water only, and the
    isolation case builds its cast in the second tenant — defaulting to
    electric makes those fail with `metering.service_not_enabled`, which is a
    real rule correctly refusing and reads exactly like a bug in this wave.
    """
    from apps.customers import models as customer_models
    from tests.test_us_met_helpers import make_premises, make_unit

    status = customer_models.AccountStatus.objects.get(tenant=tenant, code="active")
    premises = make_premises(actor, address_line="500 Main St", services_available=[service])
    unit = make_unit(actor, premises["id"], label="200", services=[service])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        account_no=account_no,
        status=status,
        account_type=customer_models.AccountType.objects.first(),
    )


def _issue(tenant, account, *, invoice_no=BILL_NO, total="142.1800", status="issued"):
    from apps.billing import models as billing_models

    today = timezone.now().date()
    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        invoice_no=invoice_no,
        status=status,
        bill_type="cycle",
        issued_at=timezone.now(),
        service_date=today,
        period_start=today,
        period_end=today,
        currency="USD",
        total=Decimal(total),
    )


@pytest.fixture()
def invoice_cloud(brazos, dana):
    """A live connection, a key with the WRITE scope, an account and a bill."""
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        connection = _connect(brazos, dana)
        account = _account(brazos, dana)
        invoice = _issue(brazos, account)
    return connection, account, invoice


def _payments(tenant):
    from apps.payments import models as payment_models

    return payment_models.Payment.objects.filter(tenant=tenant)


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE HAPPY PATH — what a partner can now do that they could not
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_invoice_cloud_posts_a_payment_and_it_lands_on_the_account(brazos, invoice_cloud):
    """One POST → one payment, `posted`, on the right account, for $142.18.

    Every figure here is the worked case the Product Owner was shown on
    2026-09-24 and nothing is computed by the test: `142.18` in, `"142.18"`
    back, `TID161007` echoed.
    """
    _connection, account, _invoice = invoice_cloud

    response = _post(brazos)
    assert response.status_code == 200, _bytes(response)
    body = json.loads(_bytes(response))

    # ⚠ **NOT A LITERAL PREFIX.** The stem is the TENANT's own number series
    # (`BR-TEN-035`), which this fixture's utility spells `PY-`; asserting
    # `PMT-` would be this test deciding a tenant's configuration. What is
    # actually being claimed is that the number we answered IS the number on
    # the row, which is the thing a partner will quote back at a clerk.
    assert body["payment_no"]
    # ⚠ `posted` — `CR-186-BRC10`, PO 2026-10-21, `OQ-PAY-12627` answered:
    # *"we have to return posted and internal status also should be posted"*.
    # This asserted `processing` until that ruling; it is our own status, not
    # a translation of theirs.
    assert body["status"] == "posted"
    # Hard rule 2 — money DISPLAYED to two decimals, as a STRING. A JSON
    # number would be a float on the far end.
    assert body["amount"] == "142.18"
    assert body["currency"] == "USD"
    assert body["payment_reference"] == REFERENCE
    assert body["duplicate"] is False

    with tenant_ctx(brazos):
        payment = _payments(brazos).get()
    assert payment.account_id == account.pk
    assert payment.amount == Decimal("142.1800")
    assert payment.confirmation == REFERENCE
    assert payment.status == "posted"
    # `cleared` — with its date — only when the bank statement is reconciled.
    assert payment.cleared_at is None


@pytest.mark.django_db
def test_the_key_is_webhook_invoice_cloud_so_the_settlement_can_find_it(brazos, invoice_cloud):
    """⚠ **THE ONE ASSERTION THAT PROTECTS THE SETTLEMENT HALF.**

    `payments.settlements._payment_for` finds a payout's members by
    **re-composing `webhook|<provider>:<reference>` literally** — the prefix is
    typed into that function. A payment recorded under any other namespace
    would be invisible to the payout that names it: `ingest_payout` would file
    it under `MEMBER_PAYMENT_NOT_FOUND`, the payout would still be written, and
    a real bank credit would sit against a payment this product holds and
    cannot find, with nothing red.

    So this asserts the exact stored string AND then asks `_payment_for` the
    question the settlement will ask, which is the assertion a rename of the
    constant cannot slip past.
    """
    from apps.payments import settlements

    assert _post(brazos).status_code == 200

    with tenant_ctx(brazos):
        payment = _payments(brazos).get()
        assert payment.webhook_key == f"webhook:{REFERENCE}".replace(":", "|invoice_cloud:", 1)
        assert payment.webhook_key == "webhook|invoice_cloud:TID161007"
        # The settlement's own lookup, run for real.
        found = settlements._payment_for(brazos.id, ic.PROVIDER, REFERENCE)
    assert found is not None and found.pk == payment.pk, (
        "the settlement re-composes `webhook|<provider>:<reference>`; a payment keyed any "
        "other way is a bank credit with no payment behind it and nothing goes red"
    )


@pytest.mark.django_db
def test_the_date_is_midnight_in_the_utilitys_own_zone(brazos, invoice_cloud):
    """`20-06-2026` → 20 June 2026 at midnight in the TENANT's clock.

    `OQ-153`, closed by the PO on 2026-08-12, and `BR-TEN-081`. ⚠ **THE DATE
    ALONE IS NOT THE ASSERTION** — `DEF-094` is precisely the bug where the
    write path anchors at UTC while the read path uses the tenant's zone, so a
    Houston utility's *20 June* is stored as `2026-06-20T00:00:00Z` and every
    screen shows *19 June*. The instant is what is asserted.
    """
    from apps.payments import settings_seam

    assert _post(brazos).status_code == 200
    with tenant_ctx(brazos):
        payment = _payments(brazos).get()
        expected = ic.posted_moment(date(2026, 6, 20))
        zone = settings_seam.tenant_timezone()

    assert payment.posted_at == expected
    assert payment.posted_at.astimezone(zone).date().isoformat() == "2026-06-20"
    assert payment.posted_at.astimezone(zone).hour == 0
    # The payment NUMBER is minted against the POSTING date (BR-TEN-035), so a
    # backdated partner payment numbers in its own month's series.
    assert "260620" in payment.payment_no, payment.payment_no


@pytest.mark.django_db
def test_an_iso_date_is_read_too_and_means_the_same_day(brazos, invoice_cloud):
    """`2026-06-20` is accepted and is the SAME instant as `20-06-2026`.

    Not a convenience: it is what stops a reader that "tries ISO first and
    falls back" from reading `10-06-2026` as 10 June in one branch and
    something else in the other. Both spellings resolve through one function
    and are asserted equal.
    """
    assert _post(brazos, body=_body(**{ic.FIELD_DATE: "2026-06-20"})).status_code == 200
    with tenant_ctx(brazos):
        payment = _payments(brazos).get()
        # ⚠ INSIDE the context: `posted_moment` reads the UTILITY's timezone,
        # and outside one that is `AUTH-003` rather than a wrong answer — which
        # is the tenant guard doing its job on the test.
        expected = ic.posted_moment(date(2026, 6, 20))
    assert payment.posted_at == expected


# ══════════════════════════════════════════════════════════════════════════
# 2 · HARD RULE 6 — the duplicate, on the cheap path
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_a_replay_is_a_200_with_the_original_payment_and_writes_nothing(
    brazos, invoice_cloud, audit_rows
):
    """The same `payment_reference` twice → ONE payment, and a `200` both times.

    ⚠ **`PAYMENT_ALREADY_EXISTS` IS NOT AN ERROR AND THAT IS THE RULING.** A
    partner retrying after a timeout did the right thing; telling them their
    request failed is how a retry becomes a second payment. So the second call
    is a `200` carrying the ORIGINAL payment's number, `duplicate: true`.

    ⚠⚠ **THE CHEAP PATH IS ASSERTED WITH A TRIPWIRE, NOT BY COUNTING ROWS,
    AND THE FIRST DRAFT OF THIS CASE COULD NOT FAIL.** It counted
    `payment.recorded` audit rows and claimed that told the cheap path from the
    expensive one. **Proved otherwise by breaking the guard:** with
    `record_payment`'s pre-check removed, the INSERT raises `IntegrityError`
    **before** the audit row is written, the transaction rolls back, and the
    count is identical — so the case stayed GREEN over a disabled hard rule 6.
    That is `DEF-058`'s exact shape reproduced in the check written to catch it,
    and it is hard-won law 7's second habit: *ask what would make this check
    pass wrongly*.

    **What actually separates the two paths is whether the transaction is
    entered at all**, and nothing it does inside survives to be counted. So the
    NUMBER ALLOCATOR is made a tripwire: it is the first thing `record_payment`
    reaches after opening the transaction, and a replay must never get there.
    With the pre-check gone this case now fails loudly and names the reason.
    """
    first = _post(brazos)
    assert first.status_code == 200
    one = json.loads(_bytes(first))

    # ⚠ **THE CAPTURED SINK, NOT `AuditLog`.** `tests/test_us_met_helpers.py`
    # registers an autouse capture sink for the whole suite, so the rows never
    # reach the table in a test and a query against it answers ZERO however
    # broken the path is — hard-won law 7's *looking at the wrong thing*, and
    # this assertion was written that way first.
    audit_before = sum(one["action"] == "payment.recorded" for one in audit_rows)

    # ── THE TRIPWIRE ───────────────────────────────────────────────────────
    # `numbering.next_number` is the first thing `record_payment` reaches
    # INSIDE its transaction. A replay must never get there: it costs one
    # SELECT and returns. Anything that reaches this has taken the expensive
    # path, whatever the row counts say afterwards — and the row counts say
    # nothing, because everything the expensive path does rolls back.
    from apps.payments import services as payment_services

    real_next_number = payment_services.numbering.next_number

    def _refuse_to_number(*args, **kwargs):
        raise AssertionError(
            "a replay reached the number allocator, so it opened a transaction: "
            "`record_payment`'s pre-check did not catch this key. Hard rule 6's cheap "
            "layer is off, and the only thing still stopping a second payment is the "
            "unique index — which is exactly the state DEF-058 shipped in, green"
        )

    payment_services.numbering.next_number = _refuse_to_number
    try:
        second = _post(brazos)
    finally:
        payment_services.numbering.next_number = real_next_number

    assert second.status_code == 200, _bytes(second)
    two = json.loads(_bytes(second))

    assert two["duplicate"] is True
    assert two["payment_no"] == one["payment_no"], "a replay returns the ORIGINAL payment"
    assert two["amount"] == one["amount"]

    with tenant_ctx(brazos):
        assert _payments(brazos).count() == 1, "hard rule 6 — one payment, however many arrive"
    assert (
        sum(one["action"] == "payment.recorded" for one in audit_rows) == audit_before
    ), "the replay took the cheap path: no transaction, no number burnt, no audit row"


@pytest.mark.django_db
def test_a_different_reference_from_the_same_partner_is_a_second_payment(brazos, invoice_cloud):
    """The mirror of the case above, and it is the one that stops the guard
    being written too wide. A dedupe keyed on the ACCOUNT, or on the bill, or
    on the amount would pass every assertion in the replay case and silently
    refuse a customer's second genuine payment as a duplicate of their first —
    money not taken, reported as money already taken."""
    assert _post(brazos).status_code == 200
    second = _post(brazos, body=_body(**{ic.FIELD_REFERENCE: "TID161008"}))
    assert second.status_code == 200, _bytes(second)
    assert json.loads(_bytes(second))["duplicate"] is False
    with tenant_ctx(brazos):
        assert _payments(brazos).count() == 2


@pytest.mark.django_db
def test_a_payment_naming_a_bill_already_paid_in_full_is_carried_as_credit(brazos, invoice_cloud):
    """CR-186-BRC10: a payment is applied AT POSTING, so the first payment
    above can settle the named bill in full. PO 2026-10-21, specific bill:
    *"anything above what it owes becomes account credit"*. A bill that owes
    nothing therefore takes the whole second payment as credit, rather than
    refusing money the partner has already taken from the customer."""
    from apps.payments import models as payment_models

    assert _post(brazos).status_code == 200
    second = _post(brazos, body=_body(**{ic.FIELD_REFERENCE: "TID161009"}))
    assert second.status_code == 200, _bytes(second)
    with tenant_ctx(brazos):
        row = _payments(brazos).get(confirmation="TID161009")
        assert not payment_models.Allocation.objects.filter(payment=row).exists()


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE WRITE SCOPE — a read key must never create money
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_a_read_only_key_cannot_create_a_payment_and_gets_the_strangers_bytes(brazos, dana):
    """⚠ **THE CENTRAL SECURITY CASE OF THIS WAVE.**

    Every partner key in this product was read-only until this address existed.
    A key scoped exactly as they were issued before — the four reads and the
    document, derived by subtraction so it cannot go stale — posts a perfectly
    valid payment and must get **the same bytes a total stranger gets**, and
    must leave no payment behind.

    The positive half is every other case in this file; **this is the negative
    one, and without it the whole scope mechanism is untested.**
    """
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        _connect(brazos, dana, scope=_read_scope())
        account = _account(brazos, dana)
        _issue(brazos, account)

    response = _post(brazos)
    assert response.status_code == 404
    assert _bytes(response) == (
        b'{"error": "We cannot serve this request.", "code": "REFUSED"}'
    ), "a key without the write scope gets the door's one refusal, not a 403 naming the scope"
    with tenant_ctx(brazos):
        assert not _payments(brazos).exists(), "a read key created money"


@pytest.mark.django_db
def test_only_invoice_cloud_declares_the_write_operation(brazos):
    """No ERP key can reach this address, because no ERP manifest declares it.

    ⚠ **THIS IS `DEF-INT-5586` RUNNING FORWARDS.** That defect was an address
    registered, routed, tested and unreachable by every key that existed,
    because a key's scope comes from its own manifest's operations and none
    declared the operation. Here the property is wanted rather than accidental:
    exactly one manifest may open this door, and a lane adding `record_payment`
    to a second one has to make this case say so.
    """
    declaring = sorted(
        manifest.key
        for manifest in REGISTRY.all()
        if any(one.name == "record_payment" for one in manifest.operations)
    )
    assert declaring == [PARTNER], (
        "exactly one connector may take a payment through the partner door; "
        f"these declare the operation: {declaring}"
    )


@pytest.mark.django_db
def test_the_address_is_registered_and_carries_both_spellings(brazos):
    """The route exists at both spellings, and `SERVED_ROUTES` binds it to the
    operation `_admit` checks the scope against.

    ⚠ **THE SECOND HALF IS THE ONE THAT MATTERS.** A route registered beside
    the table instead of in it would be a write that never met check 5 — and
    it would pass a bare *is the address registered* assertion (hard-won law 7,
    *looking at the wrong thing*: a hold-expiry test once asserted a screen was
    registered at an address the router was mounting elsewhere)."""
    from apps.integrations import partner_urls

    spellings = {
        str(one.pattern) for one in partner_urls.urlpatterns if "make-payment" in str(one.pattern)
    }
    assert spellings == {"partner/v1/make-payment", "partner/v1/make-payment/"}
    assert partner_api.SERVED_ROUTES["make-payment"][0] == "record_payment"
    assert partner_urls.PARTNER_ROUTES["make-payment"] is partner_api.partner_make_payment


# ══════════════════════════════════════════════════════════════════════════
# 4 · BR-INT-044 — seven refusals, one refusal
# ══════════════════════════════════════════════════════════════════════════


def _scope_refusal(brazos, dana):
    """The SEVENTH cause, which exists only at this address: a live key for a
    live utility from an allowed address, **without the write scope**."""
    with tenant_ctx(brazos):
        rows = models.IntegrationCredential.objects.filter(
            connection__provider_key=PARTNER
        )
        rows.update(scope=_read_scope())
    started = time.monotonic()
    response = _post(brazos)
    elapsed = time.monotonic() - started
    with tenant_ctx(brazos):
        rows.update(scope=_write_scope())
    return ("a key without the write scope", serve.CODE_OPERATION_NOT_IN_SCOPE, response, elapsed)


@pytest.mark.django_db
def test_the_seven_refusals_at_the_write_door_are_one_refusal(brazos, dana, invoice_cloud):
    """⚠ **THE CENTRAL ASSERTION, AT THE ADDRESS THAT CREATES MONEY.**

    Seven ways of being turned away, compared on the three axes an attacker can
    measure: the same BYTES, the same STATUS, the same TIME.

    ⚠ **SIX OF THE SEVEN ARE `_six_refusals`, IMPORTED FROM THE READ SUITE AND
    NOT RE-IMPLEMENTED.** That helper is the repo's own proof of this property
    and it sets each cause up so exactly one is true, times it, and puts the
    world back. Writing a private copy here would be a looser check that could
    drift from the strict one and pass while the strict one failed — and there
    would be no way to tell which surface was right. It walks the READ address
    with its own `erp_workday` key; the point of comparing against it is that
    **the write door's refusal must be byte-identical to the read door's**, or
    a caller could tell the two apart and learn that a write address exists.

    The seventh is this address's own and cannot exist on a read: a key that
    may read everything and may not take a payment.
    """
    seventh = _scope_refusal(brazos, dana)
    refusals = (
        list(
            _six_refusals(
                brazos,
                dana,
                provider=PARTNER,
                probe=lambda **kwargs: _post(brazos, **kwargs),
            )
        )
        + [seventh]
    )
    assert len(refusals) == 7

    statuses = {one[2].status_code for one in refusals}
    bodies = {_bytes(one[2]) for one in refusals}
    assert statuses == {404}, f"a second status is an oracle: {statuses}"
    assert len(bodies) == 1, (
        "seven different bodies is an oracle — a caller holding a stolen key would read "
        f"which guard refused, and whether a write door exists: {bodies}"
    )
    assert list(bodies)[0] == (
        b'{"error": "We cannot serve this request.", "code": "REFUSED"}'
    ), "the code on the wire is a CONSTANT; the cause lives in the run row"

    for name, _code, _response, elapsed in refusals:
        assert elapsed >= serve.REFUSAL_FLOOR_S, (
            f"{name} answered in {elapsed:.4f}s, under the {serve.REFUSAL_FLOOR_S}s floor — "
            "a faster refusal is a refusal that tells the caller which one they got"
        )


@pytest.mark.django_db
def test_a_refused_write_is_recorded_with_its_cause_where_a_manager_reads_it(
    brazos, dana, invoice_cloud
):
    """The cause a partner is not told is on the run row, which is the whole
    argument for the indistinguishable body (`BR-INT-044`): withheld from an
    attacker, available to a manager on S142."""
    _scope_refusal(brazos, dana)
    with tenant_ctx(brazos):
        row = (
            models.IntegrationRun.objects.filter(operation="record_payment")
            .order_by("-started_at")
            .first()
        )
    assert row is not None, "a refused write must still leave a record"
    assert serve.CODE_OPERATION_NOT_IN_SCOPE in {one["ref"] for one in row.items}
    assert row.attempted == 0


@pytest.mark.django_db
def test_a_stranger_is_refused_before_the_body_is_read_at_all(brazos, invoice_cloud):
    """`BR-INT-021` — authenticate before the body is trusted.

    A body that is not even a JSON object must still get the DOOR's refusal
    from a caller with no key, and not the payload's `400`. A `400` about a
    field name handed to an unauthenticated caller tells them the address is
    real and what its parameters are called, which is the oracle `_admit_then`
    was written to close on the read side.
    """
    response = _post(brazos, key=None, body=["not", "an", "object"])
    assert response.status_code == 404
    assert _bytes(response) == b'{"error": "We cannot serve this request.", "code": "REFUSED"}'


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE PAYLOAD — specific refusals, reachable only past the door
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body,code",
    [
        ({ic.FIELD_REFERENCE: ""}, ic.CODE_FIELD_REQUIRED),
        ({ic.FIELD_ACCOUNT: ""}, ic.CODE_FIELD_REQUIRED),
        ({ic.FIELD_BILL: ""}, ic.CODE_FIELD_REQUIRED),
        ({ic.FIELD_METHOD: ""}, ic.CODE_FIELD_REQUIRED),
        ({ic.FIELD_AMOUNT: "nought"}, ic.CODE_BAD_AMOUNT),
        ({ic.FIELD_AMOUNT: "0"}, ic.CODE_BAD_AMOUNT),
        ({ic.FIELD_AMOUNT: "-142.18"}, ic.CODE_BAD_AMOUNT),
        ({ic.FIELD_DATE: "the twentieth"}, ic.CODE_BAD_DATE),
        ({ic.FIELD_CURRENCY: "DOLLARS"}, ic.CODE_BAD_CURRENCY),
        ({ic.FIELD_ACCOUNT: "A-NOPE"}, ic.CODE_ACCOUNT_NOT_FOUND),
        ({ic.FIELD_BILL: "INV-NOPE"}, ic.CODE_BILL_NOT_FOUND),
        ({ic.FIELD_METHOD: "carrier_pigeon"}, ic.CODE_PAYMENT_REFUSED),
        ({ic.FIELD_METHOD: "cash"}, ic.CODE_METHOD_NEEDS_A_TILL),
    ],
)
def test_a_payload_this_product_cannot_take_is_refused_by_name(brazos, invoice_cloud, body, code):
    """Specific, and SAFE to be specific: reachable only past all eight checks.

    A caller that forgot a field has a bug in their JSON, and handing them the
    same five words a stolen key gets would send their engineer to look at
    their credentials.

    ⚠ **AND NOTHING IS WRITTEN BY ANY OF THEM.** The count is asserted, because
    a refusal that leaves a half-made payment behind is worse than one that
    does not refuse at all.
    """
    # `""` rather than absent, so `_body` keeps the key and the reader meets an
    # EMPTY value — which is the case a `if name in body` check would miss.
    response = _post(brazos, body=_body(**body))
    assert response.status_code in (400, 422), _bytes(response)
    assert json.loads(_bytes(response))["code"] == code
    with tenant_ctx(brazos):
        assert not _payments(brazos).exists()


@pytest.mark.django_db
def test_another_utilitys_bill_is_the_same_answer_as_no_such_bill(brazos, lonestar, dana):
    """⚠ **AN ENUMERATION ORACLE ON A MONEY DOCUMENT, CLOSED STRUCTURALLY.**

    A bill of Lone Star Ridge's, posted against a Brazos Bend account on a
    Brazos Bend key, must answer **exactly what an invented number answers**.
    If the two differed a partner could walk our invoice numbers and learn
    which exist and who owns them.

    It is not a comparison we make and then hide: the lookup is narrowed to
    THIS account inside `billing_seam.collectable()`, which filters on
    `tenant_id`, so all three cases leave through one `.first()` that returned
    `None`.
    """
    serve.reset_partner_limits()
    with tenant_ctx(lonestar):
        other_account = _account(lonestar, dana, account_no="A-99999")
        _issue(lonestar, other_account, invoice_no="INV-2026-09999")
    with tenant_ctx(brazos):
        _connect(brazos, dana)
        account = _account(brazos, dana)
        _issue(brazos, account)

    theirs = _post(brazos, body=_body(**{ic.FIELD_BILL: "INV-2026-09999"}))
    invented = _post(brazos, body=_body(**{ic.FIELD_BILL: "INV-2026-00000"}))

    assert _bytes(theirs) == _bytes(invented), (
        "another utility's bill and an invented one must be one answer, or the numbers "
        "can be walked"
    )
    assert theirs.status_code == invented.status_code == 400
    with tenant_ctx(brazos):
        assert not _payments(brazos).exists()
    with tenant_ctx(lonestar):
        assert not _payments(lonestar).exists()


@pytest.mark.django_db
def test_a_void_bill_takes_no_money(brazos, dana):
    """`void` and `corrected` are in the READ vocabulary and not in this one.

    A finance system that posted the original needs to be told a bill was
    voided, which is why `billing_seam.COLLECTABLE_STATUSES` carries them.
    Money may not be taken against a document the utility has withdrawn, which
    is why `OPEN_TO_PAYMENT` does not.
    """
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        _connect(brazos, dana)
        account = _account(brazos, dana)
        _issue(brazos, account, status="void")

    response = _post(brazos)
    assert response.status_code == 400
    assert json.loads(_bytes(response))["code"] == ic.CODE_BILL_NOT_FOUND
    with tenant_ctx(brazos):
        assert not _payments(brazos).exists()


# ══════════════════════════════════════════════════════════════════════════
# 6 · THE TILL AND THE BATCH — PO ruling 2026-09-23
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_payment_belongs_to_no_till_and_to_the_days_invoice_cloud_batch(
    brazos, invoice_cloud
):
    """`counter_session_id` NULL; `deposit_batch_id` STAMPED AT POSTING.

    ⚠ **AMENDED 2026-10-21 (`CR-186-BRC10`).** This case was
    `test_the_payment_belongs_to_no_till_and_no_deposit_batch` and asserted
    the batch NULL even after the day's cut, because a `processing` payment
    was never swept. The PO ruled the opposite the same day: *"one batch ID
    per till or per provider, per day"*, stamped *"the moment the payment is
    posted, for every method"*. So the till stays NULL (a partner has no
    drawer, PO 2026-09-23 §3.4) and the batch does NOT — and the reply names
    the batch the row carries, which is the half a partner reconciles on.
    """
    response = _post(brazos)
    assert response.status_code == 200, _bytes(response)
    body = json.loads(_bytes(response))
    with tenant_ctx(brazos):
        payment = _payments(brazos).get()
    assert payment.counter_session_id is None, "an Invoice Cloud payment touched a drawer"
    assert payment.deposit_batch_id is not None, (
        "an Invoice Cloud payment was posted with no deposit batch; PO 2026-10-21 stamps "
        "the day's provider batch at posting"
    )
    assert body["deposit_batch_id"] == str(payment.deposit_batch_id)
    assert body["deposit_batch_code"], "the reply names no batch code a partner can quote"


# ══════════════════════════════════════════════════════════════════════════
# 7 · ACCEPTED, IGNORED, RECORDED — and NOT HONOURED
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tenant_id_and_company_id_are_accepted_ignored_and_recorded(brazos, invoice_cloud):
    """PO 2026-09-17: *"we cannot tell tenant ID outside our system"*.

    ⚠ **ASSERTING A `200` WITH A GOOD `company_id` WOULD PROVE NOTHING** — that
    was true before the filter was removed. The only assertion that tells
    *ignored* from *still checked and happening to match* is that a body naming
    a DIFFERENT utility and a nonsense string produces the same outcome as one
    naming nothing, and that what they named is on the run row.
    """
    wrong = _post(brazos, body=_body(**{ic.FIELD_COMPANY: "999", ic.FIELD_TENANT: "not-a-uuid"}))
    assert wrong.status_code == 200, _bytes(wrong)

    with tenant_ctx(brazos):
        row = (
            models.IntegrationRun.objects.filter(operation="record_payment")
            .order_by("-started_at")
            .first()
        )
    assert "they named 999" in row.summary, row.summary


@pytest.mark.django_db
def test_a_claimed_late_fee_waiver_is_recorded_and_not_honoured(brazos, invoice_cloud):
    """`BR-PAY-1150`, PO 2026-09-17: *"Can a partner waive a late fee? - no"*.

    The payment is TAKEN — the money is real at their end and a customer cannot
    un-pay it — and the waiver is not acted on. The claim lands on the run row
    so the discrepancy is ours to see first rather than the partner's to
    report, which is the judgment the decision log of 2026-09-17 recorded for
    the feed and which applies unchanged to a push.
    """
    response = _post(brazos, body=_body(**{ic.FIELD_LATE_FEE_WAIVED: True}))
    assert response.status_code == 200, _bytes(response)

    unavailable = {one["code"] for one in json.loads(_bytes(response))["unavailable"]}
    assert "late_fee_waiver_is_not_honoured" in unavailable

    with tenant_ctx(brazos):
        row = (
            models.IntegrationRun.objects.filter(operation="record_payment")
            .order_by("-started_at")
            .first()
        )
    assert "they claimed a late-fee waiver" in row.summary, row.summary


@pytest.mark.django_db
def test_the_payment_is_applied_to_its_bill_at_posting_and_the_reply_says_posted(
    brazos, invoice_cloud
):
    """⚠ **REVERSED 2026-10-21 (`CR-186-BRC10`).** This case was
    `test_the_response_never_claims_the_money_reached_the_books` and asserted
    the opposite of every line below: no allocation, no journal entry, a
    `recorded_as_processing_not_cleared` note, and `status != "posted"`. The PO
    answered `OQ-PAY-12627` `posted` and ruled that every payment is applied
    and journalled at posting — Invoice Cloud's own ask, *"apply to the bill
    immediately"*. So the note is GONE (a live false sentence otherwise), the
    late-fee one stays, and the bill it names is paid by specific-bill
    application."""
    _connection, _account_row, invoice = invoice_cloud
    response = _post(brazos)
    body = json.loads(_bytes(response))
    unavailable = {one["code"] for one in body["unavailable"]}
    assert "recorded_as_processing_not_cleared" not in unavailable
    assert unavailable == {"late_fee_waiver_is_not_honoured"}
    assert body["status"] == "posted"
    with tenant_ctx(brazos):
        payment = _payments(brazos).get()
        assert payment.journal_entry_id is not None, "a posted payment wrote no journal entry"
        applied = {(str(row.invoice_id), row.amount) for row in payment.allocations.all()}
    assert applied == {(str(invoice.pk), Decimal("142.1800"))}, applied


# ══════════════════════════════════════════════════════════════════════════
# 8 · HARD RULE 7 — who did it
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_audit_row_names_the_connector_and_no_user(brazos, invoice_cloud, audit_rows):
    """`actor_user_id` NULL, `actor_kind` `integration`, `actor_label` the
    connection's own name.

    A payment row carries no `created_by` by design — who did it lives in
    `audit_log`, every time. For a partner payment the actor is not a person,
    and a blank would be the one thing hard rule 7 exists to prevent: money
    recorded with no record of how it got here.
    """
    assert _post(brazos).status_code == 200
    # ⚠ **THE CAPTURED SINK.** The suite's autouse fixture replaces the store,
    # so `AuditLog.objects` answers zero rows whatever happened — a query
    # against the table would pass this case on a build that writes no trail
    # at all.
    recorded = [one for one in audit_rows if one["action"] == "payment.recorded"]
    assert len(recorded) == 1, "hard rule 7 — one money action, one row"
    row = recorded[0]
    assert row["actor_user_id"] is None
    assert row["actor_kind"] == "integration"
    assert row["actor_label"] == "InvoiceCloud"
    assert row["tenant_id"] == brazos.id
    # The trail carries the key facts a manager would ask about, and never the
    # KEY itself — that is the masked hint on the run row.
    assert row["after"]["idempotency_key"] == "webhook|invoice_cloud:TID161007"
    assert row["after"]["confirmation"] == REFERENCE
    assert row["after"]["counter_session_id"] is None
    # CR-186-BRC10 (PO 2026-10-21): one batch per provider per day, stamped AT
    # POSTING, so the trail names the Invoice Cloud day batch it joined.
    assert row["after"]["deposit_batch_id"] is not None


@pytest.mark.django_db
def test_the_run_row_is_an_inbound_write_and_not_a_read(brazos, invoice_cloud):
    """A write filed under `inbound_read` would put *they took data from us* on
    a manager's access log for a call that put money INTO this utility — two
    opposite facts under one word, found only when somebody is reconciling."""
    assert _post(brazos).status_code == 200
    with tenant_ctx(brazos):
        row = models.IntegrationRun.objects.filter(operation="record_payment").get()
    assert row.direction == models.RUN_DIRECTION_INBOUND
    assert row.trigger == "partner"
    assert row.attempted == 1 and row.succeeded == 1
    assert HINT in row.summary, "the run row names the masked HINT and never the key"
    assert KEY not in row.summary


# ══════════════════════════════════════════════════════════════════════════
# 9 · HARD RULE 1 — one utility's key writes one utility's money
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_a_key_writes_only_into_the_utility_it_was_issued_for(brazos, lonestar, dana):
    """Both utilities hold an account `A-10650` and a bill `INV-2026-00412`,
    and the Brazos key writes into Brazos.

    ⚠ **THE SAME NUMBERS IN BOTH TENANTS IS THE WHOLE FIXTURE.** With different
    numbers the case passes on a build with no tenant scoping at all, because
    the other utility's rows simply would not match. Identical numbers make the
    only thing that can decide it the tenant the KEY opened.
    """
    serve.reset_partner_limits()
    with tenant_ctx(lonestar):
        other = _account(lonestar, dana)
        _issue(lonestar, other)
    with tenant_ctx(brazos):
        _connect(brazos, dana)
        mine = _account(brazos, dana)
        _issue(brazos, mine)

    assert _post(brazos).status_code == 200
    with tenant_ctx(brazos):
        assert _payments(brazos).count() == 1
        assert _payments(brazos).get().account_id == mine.pk
    with tenant_ctx(lonestar):
        assert not _payments(lonestar).exists(), "a Brazos key wrote money into Lone Star Ridge"


# ══════════════════════════════════════════════════════════════════════════
# 10 · THE PUBLISHED SPECIFICATION — what a partner builds their client FROM
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_published_specification_says_post_and_not_get(brazos, invoice_cloud):
    """⚠ **THE DOCUMENT IS WHERE A PARTNER LEARNS WHAT TO SEND, AND IT WAS
    LYING BEFORE THIS CASE EXISTED.**

    `partner_openapi` emitted a `"get"` with `from` · `to` · `page` ·
    `page_size` for EVERY operation that declared an address — true of every
    address on this surface until `record_payment` landed, and then **it
    published `GET /partner/v1/make-payment/` with four query parameters for a
    route that is a POST taking a JSON body.** A partner building their client
    from it would have built the wrong call, met our five-word refusal, and
    gone looking at their key.

    Nothing would have gone red: the endpoint works, the reads work, and no
    check compares a published document against the route it describes. That is
    hard-won law 1 with the DOCUMENT as the culprit — a comment claiming a
    guarantee, in the one place a caller is invited to read.

    **The false pass this case is written against:** asserting the path is
    PRESENT. It always was. The assertion is on the METHOD, on the absence of
    paging parameters, and on the body naming the fields the reader actually
    refuses a request without.
    """
    from rest_framework.test import APIRequestFactory

    from core import tenancy as core_tenancy

    factory = APIRequestFactory()
    request = factory.get("/api/partner/v1/openapi.json", REMOTE_ADDR=ALLOWED_ADDRESS)
    request.META["HTTP_AUTHORIZATION"] = f"Bearer {KEY}"
    request.tenant_id = brazos.id
    with core_tenancy.tenant_context(brazos.id):
        response = partner_api.partner_openapi(request)
    assert response.status_code == 200, _bytes(response)
    spec = json.loads(_bytes(response))

    entry = spec["paths"]["/partner/v1/make-payment/"]
    assert set(entry) == {"post"}, (
        f"the write is published as {sorted(entry)} — a partner reads this document to "
        "learn what to send, and a GET here is a call they cannot make"
    )
    assert "parameters" not in entry["post"], (
        "the write is published with query parameters copied from the read routes; there "
        "is no window and no paging on a single payment"
    )

    body = entry["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert body["required"] == [
        ic.FIELD_ACCOUNT,
        ic.FIELD_BILL,
        ic.FIELD_REFERENCE,
        ic.FIELD_DATE,
        ic.FIELD_AMOUNT,
        ic.FIELD_METHOD,
    ], "the document's required fields must be the ones the reader actually refuses without"
    # …and the five READ addresses are untouched by any of it.
    assert set(spec["paths"]["/partner/v1/bills"]) == {"get"}
    assert "parameters" in spec["paths"]["/partner/v1/bills"]["get"]


@pytest.mark.django_db
def test_every_connector_this_door_serves_can_hold_a_key_and_the_kiosk_cannot():
    """⚠ **`DEF-INT-6490` — THE SET OF CONNECTORS WHOSE KEYS MAY OPEN THIS
    DOOR, ASSERTED IN BOTH DIRECTIONS, BECAUSE IT HAS NOW BEEN WRONG TWICE IN
    ONE DAY AND IN OPPOSITE DIRECTIONS.**

    First it required EVERY operation to be `out · them`, so declaring the
    write dropped Invoice Cloud and its six LIVE READ addresses would have
    refused their own customer's key. Then it required a `/partner/v1/`
    address, so the four ERPs that declare none — `erp_workday`, `erp_sap`,
    `erp_infor`, `erp_msgp` — were dropped instead, and **that one was
    pushed**: every Workday, SAP, Infor and MSGP key on the branch was refused
    with the five words for two hours.

    **Both were derived, and neither had a case of its own**; what caught the
    first was a sibling test naming Invoice Cloud and what caught the second
    was 17 partner cases going red on a run the lane had not yet read.

    **The false pass this is written against:** asserting a COUNT, or asserting
    that one connector is present. A count passes when one connector is swapped
    for another; one name passes while four others are missing. So it asserts
    the set is exactly *every manifest declaring an operation this door serves*
    — computed from `SERVED_ROUTES`, which is the same fact the door checks a
    key's scope against — and, separately and by name, that the payment KIOSK
    is NOT in it, because the kiosk also holds a key we issued and is reached
    at a different door with a different authenticator (`_status_for` cannot
    choose between its `401` and an ERP's `404`, and answered `500` to every
    refusal the one time it had to).
    """
    served = {name for name, _label in partner_api.SERVED_ROUTES.values()}
    expected = {
        manifest.key
        for manifest in REGISTRY.all()
        if manifest.auth.mode == "they_hold_ours"
        and any(one.name in served for one in manifest.operations)
    }
    actual = set(partner_api.partner_provider_keys())

    assert actual == expected, (
        "a connector that declares an operation this door serves cannot open it, or one "
        f"that declares none can. missing: {sorted(expected - actual)}; "
        f"unexpected: {sorted(actual - expected)}"
    )
    assert PARTNER in actual, "Invoice Cloud lost its own door when the write was declared"
    assert {"erp_workday", "erp_sap", "erp_infor", "erp_msgp", "erp_aclarian"} <= actual, (
        "an ERP connector was dropped from the partner door — every key on it is refused "
        "with the five words, which reads to its owner as a bad key (DEF-INT-6490)"
    )
    assert "payments_kiosk" not in actual, (
        "the kiosk is a different door with a different authenticator, and it declares "
        "`refused: 401` where these declare `404` — `_status_for` cannot choose, and the "
        "one time it had to, every refusal on this surface came back 500"
    )

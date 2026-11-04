# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-004 (EP-CWP-02) — check and pay. Screen: CWP-003, and the
#           half of it that was never wired: `gateway.charge_guest_bill`.
# Rules:    BR-PAY-001 (default allocation = OLDEST open bill) · BR-PAY-013
#           (the cash-only privilege sanction) · BR-PAY-026 (method is a tenant
#           lookup) · BR-PAY-028 (idempotency) · BR-CWP-021 (a guest sees an
#           amount and a status, never a person) · BR-CWP-023 (five wrong
#           pairs) · BR-CWP-056 (a control that may not be used is refused with
#           its reason) · BR-INT-018 (an unconfirmed run is not a green word) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · rule 2 (four decimals) ·
#           rule 4 (no UPDATE/DELETE on a payment) · rule 6 (idempotency) ·
#           rule 7 (every money action writes `audit_log`)
# Tests:    this file, plus tests/test_us_cwp_004_guest_charge_pg.py for the
#           half the default suite cannot run. tests/test_us_cwp_004_pay.py
#           asserts what the EDGE hands the rails, against a recorder; this one
#           deletes the recorder and runs the REAL rails end to end — seam,
#           gateway, provider, settlement, allocation, ledger and audit row.
# Impacts:  apps/payments/gateway.charge_guest_bill ·
#           apps/payments/billing_seam.account_for_bill_number ·
#           apps/portal/guest_api.bill_pay
# ───────────────────────────────────────────────────────
"""A stranger presses Pay, and the money actually lands somewhere.

⚠ **THERE IS NO FAKE GATEWAY IN THIS FILE, AND THAT IS THE WHOLE POINT.**
`test_us_cwp_004_pay.py` synthesises `apps.payments.gateway` and asserts the
ARGUMENT LIST the edge hands it — which is the right test for an edge whose
rails did not exist, and which passed happily for two days while
`charge_guest_bill` was a function nobody had written. A recorder cannot tell a
wired call from an unwired one: it answers whatever it was built to answer.

So every case here connects a real (sandbox) provider, calls the real edge, and
then **counts rows in `payments`** — because the questions this story actually
turns on are *how many payments exist* and *what did they meet*, and neither is
answerable from a return value.

⚠ **THE TIMEOUT CASE IS THE ONE THAT MATTERS MOST AND IT ASSERTS AN ABSENCE.**
`US-CWP-004` TC-7 — *"a zero is a claim nobody can make"*. An absence is
invisible to every check this repo has (CLAUDE.md hard rule 8's lesson), so it
is counted here, before and after, rather than inferred from a status code.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.integrations import models as integration_models
from apps.integrations.adapters import payments_sandbox
from apps.payments import billing_seam, gateway, models as payment_models
from apps.portal import guest_api, lockout
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    an_issued_bill,
    elm_street_account,
    switch_on,
)
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: `US-CWP-004` §4's own figures. Nothing here is invented for a test.
AUGUST = date(2026, 8, 30)
DUE = date(2026, 9, 14)
BILL = "BL-2608-0141"
OWING = "142.1800"
POSTCODE = "78702"
WRONG_POSTCODE = "78704"

#: The OLDER bill BR-PAY-001 sends the money to first. `US-CWP-045` §4's own
#: July figures, so the two stories price the same customer.
JULY = date(2026, 7, 31)
JULY_BILL = "BL-2607-0139"
JULY_OWING = "18.0000"

#: `BR-CWP-057` — a token, a brand and a last four. ⚠ **NO CARD NUMBER APPEARS
#: ANYWHERE IN THIS FILE.**
INSTRUMENT = {"token": "tok_sandbox_8812", "brand": "visa", "last_four": "8812"}

#: The browser's per-visit token (`draftToken.ts`). The SAME string on a retry
#: is what makes hard rule 6 testable at all.
ATTEMPT = "5f8c0f1e-0000-4000-8000-0000000008841"

ADDRESS = "203.0.113.7"
GUESSER = "198.51.100.10"

SANDBOX = payments_sandbox.PaymentsSandboxAdapter.key


# ═══════════════════════════════════════════════════════════════════════════
# The fixture — a utility that has connected a payments provider, and a bill
# somebody is holding
# ═══════════════════════════════════════════════════════════════════════════


def a_provider(tenant, *, behaviour: str = payments_sandbox.APPROVE):
    """The tenant's payments connection. ⚠ **`behaviour` IS THE WHOLE POINT.**

    Set it to `timeout` and the product's REAL refusal path runs — the one that
    writes nothing — rather than a unit test asserting a branch nobody has ever
    seen on screen.
    """
    return integration_models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=SANDBOX,
        label="Test payments",
        environment=integration_models.ENVIRONMENT_SANDBOX,
        status=integration_models.STATUS_WORKING,
        cadence=integration_models.CADENCE_MANUAL,
        config={"behaviour": behaviour},
    )


def a_holder(tenant, actor, *, with_july: bool = False):
    """Maria's account at `1408 Elm St · A`, its August bill, and its postcode.

    The July bill is optional because BR-PAY-001's oldest-first walk is the one
    behaviour a single-bill fixture cannot show.
    """
    switch_on(tenant, actor)
    account = elm_street_account(tenant, actor)
    with tenant_context(tenant.id):
        if with_july:
            an_issued_bill(
                tenant, account, number=JULY_BILL, total=JULY_OWING, issued_on=JULY, due_on=JULY
            )
        august = an_issued_bill(
            tenant, account, number=BILL, total=OWING, issued_on=AUGUST, due_on=DUE
        )
    return account, august


def _body(**overrides):
    body = {
        "postcode": POSTCODE,
        "amount": OWING,
        "instrument": dict(INSTRUMENT),
        "receipt_email": None,
        "attempt_token": ATTEMPT,
    }
    body.update(overrides)
    return body


def _pay(tenant, number=BILL, body=None, address=ADDRESS):
    return api_call(
        guest_api.bill_pay,
        "post",
        f"/api/{tenant.subdomain}/portal/public/bills/{number}/pay",
        tenant=tenant,
        data=_body() if body is None else body,
        headers={"X-Forwarded-For": address},
        number=number,
    )


def _payments(tenant):
    with tenant_context(tenant.id):
        return list(payment_models.Payment.objects.filter(tenant_id=tenant.id))


def _allocations(tenant):
    with tenant_context(tenant.id):
        return list(
            payment_models.Allocation.objects.filter(tenant_id=tenant.id).order_by("created_at")
        )


# ══ THE HOLE ITSELF — the rails exist and the edge reaches them ════════════


def test_the_gateway_publishes_the_guest_charge_its_own_docstring_records():
    """⚠ **THIS IS THE DEFECT, AS ONE LINE.**

    `apps/portal/guest_api.bill_pay` calls `gateway.charge_guest_bill(...)`.
    Until this lane it did not exist, the `AttributeError` was swallowed by that
    edge's `except Exception`, and a stranger who pressed Pay got **503 · the
    provider was silent** — a sentence about somebody else's system, for a
    function we had not written.
    """
    assert callable(getattr(gateway, "charge_guest_bill", None))


def test_the_edge_resolves_the_rails_through_sys_modules(monkeypatch):
    """⚠ **A SIBLING SUITE'S STAND-IN MUST ACTUALLY BE THE THING THAT RUNS.**

    `test_us_cwp_004_pay.py` and `test_us_cwp_005_receipt.py` install a recorder
    with `monkeypatch.setitem(sys.modules, "apps.payments.gateway", …)` and
    assert what the edge hands it. That works only if the edge resolves the
    module through `sys.modules`; `from apps.payments import gateway` reads the
    PACKAGE ATTRIBUTE instead, which any earlier import has already bound to the
    real module, and the recorder is then never called at all.

    **It was live on the tip and it hid behind test ordering:**
    `test_us_cwp_004_pay.py` passed alone and failed beside
    `test_us_cwp_045_pay_now.py` — which imports the real module at collection —
    with three cases asserting against rails they thought they had replaced.
    This is the assertion that stops it coming back, and it needs no database.
    """
    import sys
    import types

    from apps.portal import guest_api as edge

    stand_in = types.ModuleType("apps.payments.gateway")
    monkeypatch.setitem(sys.modules, "apps.payments.gateway", stand_in)
    assert edge._rails() is stand_in


# ══ THE SEAM — bill number → the account it belongs to ═════════════════════


def test_the_seam_answers_which_account_a_bill_number_belongs_to(pine_hill, sarah):
    """`invoices.account_id` is a FACT — one bill belongs to one account.

    What was missing was payments' permission to READ it, not the answer.
    """
    account, august = a_holder(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        owner = billing_seam.account_for_bill_number(BILL)

    assert owner is not None
    assert str(owner.account_id) == str(account.pk)
    assert str(owner.invoice_id) == str(august.pk)
    assert owner.number == BILL


def test_the_seam_answers_none_for_another_utilitys_number(pine_hill, oak_ridge, sarah, elena):
    """Hard rule 1 — the tenant is IN THE QUERY, not left to RLS.

    ⚠ **THE SUITE RUNS ON SQLITE, WHICH HAS NO ROW-LEVEL SECURITY**, so a read
    that left the tenant to the database would have no test that could ever see
    it go wrong (law 14 in its second costume).
    """
    a_holder(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    with tenant_context(oak_ridge.id):
        assert billing_seam.account_for_bill_number(BILL) is None


def test_the_seam_answers_none_for_a_draft_and_for_a_void(pine_hill, sarah):
    """A bill a payment may not be taken against is refused identically to one
    that does not exist.

    ⚠ **A DRAFT CARRIES A NUMBER** (BR-BIL-063 — minted when the draft is
    created), so *"it has a number"* is not *"somebody may pay it"*. A void bill
    is no longer owed and a corrected one has been replaced (BR-BIL-014).
    """
    _, august = a_holder(pine_hill, sarah)
    for refused in (billing_models.INVOICE_DRAFT, billing_models.INVOICE_VOID):
        with tenant_context(pine_hill.id):
            august.status = refused
            august.save(update_fields=["status"])
            assert billing_seam.account_for_bill_number(BILL) is None, refused


# ══ TC-6 — one payment, allocated by the existing rule, with an audit row ══


def test_a_guest_paying_the_bill_records_exactly_one_payment(pine_hill, sarah):
    """`US-CWP-004` — `$142.18` against `BL-2608-0141` leaves ONE payment.

    ⚠ **COUNTED, NOT INFERRED FROM A 201.** The edge answered 201 for two days
    while nothing was written at all.
    """
    a_holder(pine_hill, sarah)
    a_provider(pine_hill)
    assert _payments(pine_hill) == []

    response = _pay(pine_hill)

    assert response.status_code == 201, response.data
    rows = _payments(pine_hill)
    assert len(rows) == 1
    assert rows[0].amount == Decimal(OWING)
    # Hard rule 2 — four decimals stored, and the reference a person reads down
    # a telephone is the PMT- series number, never a row id (B14 rule 31).
    assert response.data["reference"] == rows[0].payment_no
    assert response.data["amount"]["amount"] == OWING
    assert response.data["against"] == BILL


def test_the_payment_is_allocated_oldest_first_by_the_existing_rule(pine_hill, sarah):
    """`BR-PAY-001` — the default is the OLDEST open bill, and this path states
    no target of its own.

    ⚠ **THE GUEST CHOSE A BILL TO LOOK AT, NOT A BILL TO SETTLE.** `$142.18`
    arriving against August meets **July's `$18.00` first** and leaves
    `$124.18` on August. That is the signed rule, executed by the ONE allocator
    (`apps/payments/allocation.py`) that every other payment in the product goes
    through — a second walk written for the guest path would be a second answer
    to *what did this customer pay*.
    """
    a_holder(pine_hill, sarah, with_july=True)
    a_provider(pine_hill)

    assert _pay(pine_hill).status_code == 201

    rows = _allocations(pine_hill)
    assert len(rows) == 2
    by_amount = sorted(row.amount for row in rows)
    assert by_amount == [Decimal("18.0000"), Decimal("124.1800")]
    assert sum(by_amount) == Decimal(OWING)


def test_the_money_action_writes_an_audit_row_naming_a_guest_payer(pine_hill, sarah, audit_rows):
    """CLAUDE.md hard rule 7, on the one path in the product with **no `User`**.

    ⚠ **`actor_user_id` STAYS NULL AND THE PAYLOAD NAMES THE FORM.** `BR-CWP-004`
    keeps portal people and staff users apart on purpose, so inventing a user id
    would make a stranger's payment indistinguishable from a clerk's in the one
    record that exists to tell them apart. What names the actor instead is
    `portal_paid_by` — `guest_api.GUEST_PAID_BY` — beside the channel.

    ⚠ **READ THROUGH THE `audit_rows` SINK RATHER THAN OFF THE TABLE.** These
    suites install a capture sink (`test_us_met_helpers.audit_rows`, autouse),
    so `AuditLog.objects` is empty here and asserting over it would be a check
    that can never fail — which is worse than no check, because it is trusted.
    """
    a_holder(pine_hill, sarah)
    a_provider(pine_hill)

    assert _pay(pine_hill).status_code == 201

    named = [
        row
        for row in audit_rows
        if isinstance(row.get("after"), dict)
        and row["after"].get("portal_paid_by") == guest_api.GUEST_PAID_BY
    ]
    assert named, "no audit row names the guest payer (hard rule 7)"
    assert all(row["actor_user_id"] is None for row in named)
    assert all(row["after"]["channel"] == "customer_portal" for row in named)
    # The bill the person was holding travels too, so a year later somebody can
    # say WHICH piece of paper this money arrived against — which is not the
    # same question as which bill it settled (BR-PAY-001 answers that).
    assert all(row["after"]["portal_bill_number"] == BILL for row in named)
    assert all(row["tenant_id"] == pine_hill.id for row in named)


# ══ TC-7 — a provider that does not answer writes NOTHING ══════════════════


def test_a_timeout_writes_no_payment_row_at_all(pine_hill, sarah):
    """`US-CWP-004` TC-7 / `US-CWP-045` TC-6 — *an unknown outcome is not a zero*.

    ⚠ **ASSERTED BY COUNTING, IN THREE TABLES.** The provider may well have
    taken the money at the far end; what must be true is that nothing HERE
    claims a payment happened, because nobody knows whether one did.
    """
    a_holder(pine_hill, sarah)
    a_provider(pine_hill, behaviour=payments_sandbox.TIMEOUT)

    response = _pay(pine_hill)

    assert response.status_code == 503
    assert "reference" not in dict(response.data)
    assert _payments(pine_hill) == []
    assert _allocations(pine_hill) == []
    with tenant_context(pine_hill.id):
        assert not payment_models.PaymentWebhookEvent.objects.filter(
            tenant_id=pine_hill.id
        ).exists()


def test_the_retry_after_a_timeout_carries_the_same_idempotency_key(pine_hill, sarah):
    """`US-CWP-045` TC-7 — *the SAME key generated BEFORE the first request left*.

    ⚠ **A KEY MINTED AFTER AN ANSWER COMES BACK CANNOT EXIST FOR THE ONE CASE
    IT IS FOR** — the case where no answer comes back. The browser mints one
    `attempt_token` per visit to `CWP-003`, so the retry re-presents the same
    string and the provider's own idempotency refuses the second debit.

    The proof is that the key is a pure function of what the browser holds: the
    same attempt token gives the same key across two separate requests, and a
    different one does not.
    """
    a_holder(pine_hill, sarah)
    first = guest_api._attempt_key(pine_hill.id, BILL, ATTEMPT)
    retry = guest_api._attempt_key(pine_hill.id, BILL, ATTEMPT)
    other_visit = guest_api._attempt_key(pine_hill.id, BILL, "a-different-visit")

    assert first == retry
    assert first != other_visit

    # And the retry of a timed-out attempt still writes nothing, twice over.
    a_provider(pine_hill, behaviour=payments_sandbox.TIMEOUT)
    assert _pay(pine_hill).status_code == 503
    assert _pay(pine_hill).status_code == 503
    assert _payments(pine_hill) == []


def test_the_same_attempt_pressed_twice_leaves_one_payment(pine_hill, sarah):
    """CLAUDE.md hard rule 6 — a double press must never take money twice.

    ⛔ **THIS CASE ASSERTED A 409 `notPayable` FOR THE SECOND PRESS UNTIL
    2026-10-23, AND THAT WAS THE DEFECT, NOT THE RULE.** `DEF-CWP-3950` (filed
    2026-09-05, fixed `47f5e3405`) moved the attempt-key lookup (guard 5½)
    ahead of the payability re-read, because *"There is nothing to pay"* about
    a payment just made reads as *your money did not arrive*. So the second
    press now answers the FIRST receipt, the same reference, and the rails are
    not reached again. The assertion was stale from that fix on (found by lane
    PORTAL-FEE-2; both lines predate this clone's 2026-09-15 history boundary).

    The idempotency key is still what covers two presses in flight AT ONCE —
    see the case below, which drives that path directly.
    """
    a_holder(pine_hill, sarah)
    a_provider(pine_hill)

    first = _pay(pine_hill)
    second = _pay(pine_hill)

    assert first.status_code == 201
    assert second.status_code == 200, second.data
    assert second.data["reference"] == first.data["reference"]
    rows = _payments(pine_hill)
    assert len(rows) == 1, "the same attempt twice must leave ONE payment"
    assert rows[0].amount == Decimal(OWING)


def test_two_attempts_in_flight_at_once_settle_onto_one_payment(pine_hill, sarah):
    """CLAUDE.md hard rule 6 — the case the payability guard structurally cannot
    catch, driven through the rails directly.

    ⚠ **THIS IS WHAT TWO CONCURRENT PRESSES REACH.** Both requests re-read a
    payable bill before either commits, so both arrive at
    `gateway.charge_guest_bill` carrying the SAME key the browser minted for
    that visit. What collapses them is `settle_charge`'s
    `uq_payment_webhook_events_event`, with `uq_payments_webhook_key` beneath
    it — two independent guards, neither trusted because the other exists
    (DEF-058), and **neither re-implemented by this lane**.
    """
    account, _ = a_holder(pine_hill, sarah)
    a_provider(pine_hill)
    key = guest_api._attempt_key(pine_hill.id, BILL, ATTEMPT)

    def once():
        with tenant_context(pine_hill.id):
            return gateway.charge_guest_bill(
                pine_hill.id,
                bill_number=BILL,
                amount=Decimal(OWING),
                currency="USD",
                instrument=dict(INSTRUMENT),
                receipt_email=None,
                channel="customer_portal",
                paid_by=guest_api.GUEST_PAID_BY,
                idempotency_key=key,
            )

    first = once()
    second = once()

    assert len(_payments(pine_hill)) == 1, "one key must leave ONE payment"
    assert first["reference"] == second["reference"]
    # And the second one allocated nothing a second time, so the bill is not
    # over-settled and no credit was invented out of a replay.
    assert sum(row.amount for row in _allocations(pine_hill)) == Decimal(OWING)


# ══ A DECLINE IS NOT A FAILURE AND NOT A RECEIPT ═══════════════════════════


def test_a_declined_card_writes_nothing_and_does_not_read_as_silence(pine_hill, sarah):
    """`BR-INT-018` — *declined* and *no answer* are different facts.

    A decline means the provider answered and refused: no money moved and the
    customer's bills are exactly as they were. Answering **503 · the card
    service did not answer** would tell them to try again against a card that
    will refuse again.
    """
    a_holder(pine_hill, sarah)
    a_provider(pine_hill, behaviour=payments_sandbox.DECLINE)

    response = _pay(pine_hill)

    assert response.status_code == 409
    assert response.data["message_key"] == "portal.quickPay.declined"
    assert _payments(pine_hill) == []


def test_an_approved_charge_we_cannot_record_never_answers_a_receipt(pine_hill, sarah):
    """⛔ **THE WORST OUTCOME ON THIS PATH, AND THE FIRST DRAFT SHIPPED A RECEIPT
    FOR IT.**

    `settle_charge` answers a rule refusal with `payment_id=None` rather than
    raising — deliberately, so the DELIVERY row stands and somebody can find
    money that really moved. `recorded.payment_no or recorded.payment_id` is
    then `None`, and that reached `guest_payment_receipt` as
    **`reference: None`**: a `201`, a receipt, a blank reference, and a customer
    told they had paid.

    Driven here through the tenant deactivating the `card` payment method,
    which is a real thing a utility can do on the Reference data page and which
    makes `record_payment` refuse under `BR-PAY-026` — the same shape as any
    other rule refusal inside the settlement.

    ⚠ **NO GATE COULD HAVE FOUND THIS.** Every type is right, every test that
    existed was green, and the failure is a `None` travelling through a dict
    into a field that accepts it.
    """
    from apps.tenancy import models as tenancy_models

    a_holder(pine_hill, sarah)
    a_provider(pine_hill)
    with tenant_context(pine_hill.id):
        tenancy_models.PaymentMethod.objects.filter(
            tenant_id=pine_hill.id, code=gateway.GUEST_METHOD_CODE
        ).update(active=False)

    response = _pay(pine_hill)

    assert response.status_code == 500
    assert response.data["message_key"] == "portal.quickPay.notRecorded"
    assert "reference" not in dict(response.data)
    assert _payments(pine_hill) == []
    # ⚠ **AND THE DELIVERY ROW STANDS**, which is the whole reason
    # `settle_charge` refuses softly: the money is real at the provider and a
    # lost row here is a payment nobody knows about.
    with tenant_context(pine_hill.id):
        deliveries = list(
            payment_models.PaymentWebhookEvent.objects.filter(tenant_id=pine_hill.id)
        )
    assert len(deliveries) == 1
    assert deliveries[0].payment_id is None


# ══ BR-CWP-056 — a utility with no processor refuses, and says nothing more ═


def test_with_no_provider_connected_the_commit_refuses_without_naming_why(pine_hill, sarah):
    """One sentence for every held reason, and that is a DISCLOSURE decision.

    ⚠ **`BR-PAY-013`'s CASH-ONLY SANCTION IS A FACT ABOUT THE CUSTOMER.**
    Telling a stranger holding the paper *"this account may not use a card"*
    says the account holder has bounced payments — which `BR-CWP-021` forbids
    on this surface as plainly as it forbids their name. So *no processor
    connected* and *this account is cash-only* answer the SAME sentence, and
    the held code travels only to the log.
    """
    a_holder(pine_hill, sarah)  # deliberately no provider connected

    response = _pay(pine_hill)

    assert response.status_code == 409
    assert response.data["message_key"] == "portal.quickPay.cannotPayHere"
    assert response.data["br_ref"] == "BR-CWP-056"
    assert _payments(pine_hill) == []


def test_a_cash_only_account_refuses_with_the_very_same_sentence(pine_hill, sarah):
    """`BR-PAY-013` — the privilege sanction is not walked round by the public
    form.

    ⚠ **THE SIGNED-IN SCREEN ALREADY HOLDS ITS PAY CONTROL FOR THIS**
    (`gateway.held_reason`, `HELD_CASH_ONLY`). A guest path that skipped the
    check would make `CWP-003` a documented way past a sanction J12 step 6 says
    no rule ever auto-clears — and the customer under it is the one person
    certain to know the form exists.
    """
    account, _ = a_holder(pine_hill, sarah)
    a_provider(pine_hill)
    with tenant_context(pine_hill.id):
        account.cash_only_no_autopay = True
        account.save(update_fields=["cash_only_no_autopay"])

    response = _pay(pine_hill)

    assert response.status_code == 409
    # Byte-identical to the no-provider refusal above — that is the point.
    assert response.data["message_key"] == "portal.quickPay.cannotPayHere"
    assert response.data["br_ref"] == "BR-CWP-056"
    assert _payments(pine_hill) == []


# ══ HARD RULE 4 — a payment row is never updated and never deleted ═════════


def test_the_whole_path_never_updates_or_deletes_a_payment(pine_hill, sarah):
    """CLAUDE.md hard rule 4, asserted over the rows rather than over the code.

    A replay, a decline and a timeout all run against a tenant that has already
    taken one payment; the first payment's id, number, amount and creation
    moment are unchanged at the end, and nothing was removed.
    """
    a_holder(pine_hill, sarah)
    connection = a_provider(pine_hill)
    assert _pay(pine_hill).status_code == 201
    before = _payments(pine_hill)
    assert len(before) == 1
    frozen = (before[0].pk, before[0].payment_no, before[0].amount, before[0].created_at)

    _pay(pine_hill)  # the replay
    with tenant_context(pine_hill.id):
        connection.config = {"behaviour": payments_sandbox.DECLINE}
        connection.save(update_fields=["config"])
    _pay(pine_hill, body=_body(attempt_token="second-visit"))
    with tenant_context(pine_hill.id):
        connection.config = {"behaviour": payments_sandbox.TIMEOUT}
        connection.save(update_fields=["config"])
    _pay(pine_hill, body=_body(attempt_token="third-visit"))

    after = _payments(pine_hill)
    assert len(after) == 1
    assert (after[0].pk, after[0].payment_no, after[0].amount, after[0].created_at) == frozen


# ══ BR-CWP-023 — the lockout is not circumventable through the rails ═══════


def test_the_five_tries_lockout_still_holds_with_the_rails_wired(pine_hill, sarah):
    """`BR-CWP-023` — five wrong pairs lock the form, and **the commit endpoint
    is the same form**.

    ⚠ **RE-PROVED AGAINST THE REAL RAILS.** `test_us_cwp_004_pay.py` asserts
    this against a recorder, which can only show that the recorder was not
    called. What must also be true is that no payment row exists — a lockout
    that refused the response while the rails ran would be no lockout at all.
    """
    a_holder(pine_hill, sarah)
    a_provider(pine_hill)

    for _ in range(5):
        assert (
            _pay(pine_hill, body=_body(postcode=WRONG_POSTCODE), address=GUESSER).status_code == 409
        )

    # The sixth is locked — and a CORRECT pair inside the window is refused too,
    # which is what makes it a lockout rather than a delay.
    locked = _pay(pine_hill, address=GUESSER)
    assert locked.status_code == 409
    assert lockout.is_locked(str(pine_hill.id), lockout.FORM_QUICK_PAY, GUESSER)
    assert _payments(pine_hill) == []


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-004 (EP-CWP-02) · US-CWP-045 TC-6/TC-7 · BR-PAY-001 ·
#         BR-PAY-013 · BR-CWP-021 · BR-CWP-023 · BR-CWP-056 · BR-INT-018 ·
#         CLAUDE.md hard rules 1, 2, 4, 6, 7 · hard-won laws 2 and 14
# generated: 2026-09-05 by the CR-068 lane F (the guest charge)
# checklist: A✔ B=n/a(tests) C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: every case here was driven RED against the branch tip in a detached
#        worktree BEFORE the rails were written (hard-won law 7) — the failure
#        was `AttributeError: module 'apps.payments.gateway' has no attribute
#        'charge_guest_bill'` surfacing as 503, quoted in the lane's report.
# exceptions:
#   E1 the PostgreSQL half of law 14 lives in
#      `tests/test_us_cwp_004_guest_charge_pg.py`, because the default suite is
#      in-memory SQLite and has no aborted-transaction state.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

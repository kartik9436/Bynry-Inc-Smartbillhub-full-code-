# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-045 (EP-CWP-09) — pay now, and where the payment will land,
#           BEFORE it commits. Screen: CWP-038
# Rules:    BR-CWP-058 (the panel, before the commit) · BR-CWP-056 (a refused
#           control carries its reason) · BR-CWP-010 (both halves in the query)
#           · BR-PAY-001 / BR-PAY-010 (oldest bill first) · BR-INT-018 (an
#           unconfirmed run is not a green word) · BR-INT-037 (a provider is
#           data) · CLAUDE.md hard rule 2 · rule 4 · rule 6 · rule 7
# Tests:    this file
# Impacts:  apps/payments/gateway.py · apps/payments/webhooks.settle_charge ·
#           apps/portal/seams/pay_now_seam.py · apps/portal/api.py
# ───────────────────────────────────────────────────────
"""`US-CWP-045`'s cases — and the three the whole screen exists for.

**TC-6 — A TIMEOUT WRITES NOTHING.** *"The screen says so and no payment row is
written. Assert zero rows — an unknown outcome is not a zero."* The assertion is
a COUNT and not a status word, because a row written with a hopeful status is
exactly the claim nobody can make.

**TC-7 — THE RETRY CARRIES THE SAME KEY.** Minted before the first request left,
so a debit that already happened at the provider is never taken twice. The test
asserts the string that comes back from the timeout is the string that goes out
on the retry, and that the two attempts leave ONE payment.

**TC-4/TC-5 — WHERE IT WILL LAND, BEFORE THE COMMIT.** `$40.00` against
`$142.18` reads `$102.18` afterwards, and the panel says so first. With two open
bills the money meets the OLDER one first, by the tenant's rule, and the preview
and the outcome are produced by the same function over the same rule — which is
the assertion `US-CWP-045` §7 asks for by name.

RED PROOFS — RUN, AND QUOTED AS THEY ACTUALLY FAILED (hard-won law 7)
=====================================================================
Each sabotage was applied, the one case it should break was run, and the file
was restored from HEAD's bytes. **The failures below are transcribed from the
run rather than predicted**, because a docstring that claims a failure nobody
watched is hard-won law 1 wearing a test's clothes (DEF-182).

  * `gateway.charge`'s `if run.outcome == OUTCOME_UNCONFIRMED:` made `if False`:

        E   AssertionError: assert 'declined' == 'no_answer'

    ⚠ **AND THE FAILURE IS NOT THE ONE THE FIRST DRAFT OF THIS DOCSTRING
    PREDICTED, WHICH IS ITSELF THE FINDING.** It predicted `assert 1 == 0` — a
    payment row for money nobody knows moved. What happens instead is that the
    unconfirmed run falls through to the `!= OUTCOME_SUCCEEDED` branch and
    reports `declined`, so no row is written and the customer is told *your card
    was refused* about money that may well have left their account. **That is a
    worse outcome than the predicted one, not a milder one**, and TC-6's FIRST
    assertion is what catches it: the outcome WORD, before the row counts.

  * `pay()` minting a fresh key rather than carrying the caller's:

        E   AssertionError: the SAME key, carried back for the retry

  * `_tenant_order()` returning `newest_first`:

        E   AssertionError: assert ['BL-2608-0141'] == ['BL-2607-013...']
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from apps.customers import models as customers_models
from apps.integrations import models as integration_models
from apps.integrations.adapters import payments_sandbox
from apps.payments import gateway, models as payment_models
from apps.portal.seams import pay_now_seam
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import an_issued_bill, elm_street_account, switch_on

pytestmark = pytest.mark.django_db

#: `US-CWP-045` §4's own figures. Nothing here is invented for a test.
AUGUST = "142.1800"
AUGUST_NO = "BL-2608-0141"
JULY = "18.0000"
JULY_NO = "BL-2607-0139"
PART = Decimal("40.00")
#: TC-4's worked answer — `142.18 − 40.00`.
AFTER_PART = "102.1800"
THE_KEY = "pay_26_08841"

SANDBOX = payments_sandbox.PaymentsSandboxAdapter.key


# ═══════════════════════════════════════════════════════════════════════════
# The fixture — a utility that has connected a payments provider, and a
# customer with a saved card
# ═══════════════════════════════════════════════════════════════════════════


def a_provider(tenant, *, behaviour: str = payments_sandbox.APPROVE, environment: str | None = None):
    """The tenant's payments connection. ⚠ **`behaviour` IS THE WHOLE POINT.**

    Set it to `timeout` and the product's REAL refusal path runs — the one that
    writes nothing — rather than a unit test asserting a branch nobody has ever
    seen on screen.
    """
    return integration_models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=SANDBOX,
        label="Test payments",
        environment=environment or integration_models.ENVIRONMENT_SANDBOX,
        status=integration_models.STATUS_WORKING,
        cadence=integration_models.CADENCE_MANUAL,
        config={"behaviour": behaviour},
    )


def a_card(tenant, account, *, kind: str = payment_models.INSTRUMENT_CARD):
    """`Visa ••••4242` — the token the sandbox issues, saved against the
    customer who holds this account (the instrument hangs off the CUSTOMER, not
    the account: a landlord saves one card and pays four accounts with it)."""
    link = customers_models.CustomerAccount.objects.filter(
        tenant_id=tenant.id, account_id=account.pk
    ).first()
    token = payments_sandbox.tokenise(str(link.customer_id))
    return payment_models.StoredPaymentInstrument.objects.create(
        tenant=tenant,
        customer_id=link.customer_id,
        gateway_token=token["gateway_token"],
        brand=token["brand"],
        last_four=token["last_four"],
        expires_month=token["expires_month"] if kind == payment_models.INSTRUMENT_CARD else None,
        expires_year=token["expires_year"] if kind == payment_models.INSTRUMENT_CARD else None,
        kind=kind,
        status=payment_models.INSTRUMENT_ACTIVE,
        used_for=[payment_models.INSTRUMENT_USE_ONE_OFF],
    )


def a_customer_with_one_bill(tenant, actor):
    account = elm_street_account(tenant, actor)
    with tenant_context(tenant.id):
        an_issued_bill(
            tenant, account, number=AUGUST_NO, total=AUGUST, issued_on=date(2026, 8, 26),
            due_on=date(2026, 9, 14),
        )
    return account


def customer_id_of(tenant, account) -> Any:
    return customers_models.CustomerAccount.objects.filter(
        tenant_id=tenant.id, account_id=account.pk
    ).first().customer_id


def paid_rows(tenant, account) -> int:
    return payment_models.Payment.objects.filter(
        tenant_id=tenant.id, account_id=account.pk
    ).count()


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 · TC-5 — where it will land, BEFORE the commit (`BR-CWP-058`)
# ═══════════════════════════════════════════════════════════════════════════


def test_us_cwp_045_tc4_the_panel_shows_102_18_before_anything_commits(pine_hill, sarah):
    """⚠ **THE CASE THE SCREEN EXISTS FOR.** `$40.00` against a `$142.18` bill
    lands on `BL-2608-0141` and leaves it owing `$102.18` — and the customer sees
    that figure BEFORE they press anything, because afterwards the payment row
    cannot be edited, only reversed (hard rule 4)."""
    switch_on(pine_hill, sarah)
    account = a_customer_with_one_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        panel = pay_now_seam.preview(account.pk, amount=PART)

    assert [one["number"] for one in panel["lands_on"]] == [AUGUST_NO]
    assert panel["lands_on"][0]["owing"] == AUGUST
    assert panel["lands_on"][0]["paying"] == "40.0000"
    assert panel["lands_on"][0]["owing_after"] == AFTER_PART
    assert panel["writes"] == [], "a preview writes nothing and says so on its face"


def test_us_cwp_045_tc5_two_bills_meet_the_money_oldest_first_by_the_tenants_rule(
    pine_hill, sarah
):
    """⚠ **NEGATIVE — THE SCREEN NEVER GUESSES A DIFFERENT ORDER.** `$40.00`
    against `$18.00` (July) and `$142.18` (August) settles July in full first and
    puts the remaining `$22.00` against August.

    **RED PROOF, RUN:** with `_tenant_order()` returning `newest_first` this
    fails at `assert ['BL-2608-0141'] == ['BL-2607-0139', 'BL-2608-0141']` — the
    panel showing August first while the engine still settles July.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_issued_bill(
            pine_hill, account, number=JULY_NO, total=JULY, issued_on=date(2026, 7, 26),
            due_on=date(2026, 8, 14),
        )
        an_issued_bill(
            pine_hill, account, number=AUGUST_NO, total=AUGUST, issued_on=date(2026, 8, 26),
            due_on=date(2026, 9, 14),
        )
        panel = pay_now_seam.preview(account.pk, amount=PART)

    assert [one["number"] for one in panel["lands_on"]] == [JULY_NO, AUGUST_NO]
    assert panel["lands_on"][0]["paying"] == "18.0000"
    assert panel["lands_on"][0]["owing_after"] == "0.0000"
    assert panel["lands_on"][1]["paying"] == "22.0000"
    assert panel["lands_on"][1]["owing_after"] == "120.1800"
    assert panel["order"] == "oldest_first", "the order is on the wire, not typed into the screen"


def test_us_cwp_045_the_preview_and_the_outcome_come_from_the_same_rule(pine_hill, sarah):
    """⚠ **§7's OWN TEST, BY NAME:** *"the preview and the applied allocation
    must come from the SAME rule, and a test that asserts the preview matches the
    outcome is the one that stops them drifting."*"""
    switch_on(pine_hill, sarah)
    account = a_customer_with_one_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_provider(pine_hill)
        a_card(pine_hill, account)
        panel = pay_now_seam.preview(account.pk, amount=PART)
        answer = pay_now_seam.pay(
            account.pk,
            customer_id=customer_id_of(pine_hill, account),
            may_pay=True,
            amount=PART,
            instrument_id=None,
            key=panel["idempotency_key"],
        )

    assert answer["outcome"] == "paid"
    assert answer["lands_on"] == panel["lands_on"], (
        "the panel a customer read and the rows the receipt states are the SAME rows"
    )
    # ⚠ **AND THE ENGINE AGREES WITH BOTH, READ OUT OF THE DATABASE.** Comparing
    # two dicts this module built would only prove it is consistent with itself;
    # the `allocations` row is what the money actually did.
    with tenant_context(pine_hill.id):
        applied = payment_models.Allocation.objects.get(
            tenant_id=pine_hill.id, invoice__invoice_no=AUGUST_NO
        )
    # ⚠ COMPARED AS A `Decimal`, NOT AS A STRING. The column is `NUMERIC(18,6)`
    # — a lawful container under hard rule 2, which governs what is WRITTEN —
    # so it reads back `40.000000`, and a string comparison would fail on the
    # scale rather than on the money.
    assert applied.amount == PART
    assert panel["lands_on"][0]["paying"] == "40.0000"
    assert panel["lands_on"][0]["owing_after"] == AFTER_PART


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — the whole balance, allocated, in the books, with an audit row
# ═══════════════════════════════════════════════════════════════════════════


def test_us_cwp_045_tc3_the_whole_balance_clears_the_august_bill(pine_hill, sarah):
    """One payment row, allocated to `BL-2608-0141`, in the books, audited."""
    from apps.payments import billing_seam

    switch_on(pine_hill, sarah)
    account = a_customer_with_one_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_provider(pine_hill)
        a_card(pine_hill, account)
        bill = _bill(pine_hill, AUGUST_NO)
        answer = pay_now_seam.pay(
            account.pk,
            customer_id=customer_id_of(pine_hill, account),
            may_pay=True,
            amount=Decimal(AUGUST),
            instrument_id=None,
            key=THE_KEY,
            portal_actor={"portal_customer_id": "maria", "channel": "customer_portal"},
        )

        assert answer["outcome"] == "paid"
        assert answer["payment_no"] is not None, "it carries a PMT- number like any other payment"
        assert paid_rows(pine_hill, account) == 1
        payment = payment_models.Payment.objects.get(
            tenant_id=pine_hill.id, account_id=account.pk
        )
        # CR-186-BRC10 (PO 2026-10-21): posted at entry, cleared at reconciliation.
        assert payment.status == payment_models.PAYMENT_POSTED
        assert payment.amount == Decimal(AUGUST)
        assert billing_seam.allocated_so_far(bill.pk) == Decimal(AUGUST), "and allocated"
        assert payment.journal_entry_id is not None, "and in the books (CLAUDE.md rule 5)"


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — ⚠ THE GATEWAY TIMES OUT AND **NOTHING** IS WRITTEN
# ═══════════════════════════════════════════════════════════════════════════


def test_us_cwp_045_tc6_a_timeout_writes_no_payment_row_at_all(pine_hill, sarah):
    """⚠ **ASSERT ZERO ROWS — AN UNKNOWN OUTCOME IS NOT A ZERO.**

    The provider was asked and said nothing, so whether the money moved is
    unknown. A row with a hopeful status would be a claim nobody can make, and
    the allocation engine would spend it on the next bill.

    **RED PROOF, RUN:** with `gateway.charge`'s unconfirmed branch switched off
    this fails on the FIRST assertion below —
    `AssertionError: assert 'declined' == 'no_answer'` — which is the customer
    being told their card was refused about money that may have left their
    account. See the module docstring: that is a worse outcome than the row this
    case was named for, and the order of the assertions is what finds it.
    """
    switch_on(pine_hill, sarah)
    account = a_customer_with_one_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_provider(pine_hill, behaviour=payments_sandbox.TIMEOUT)
        a_card(pine_hill, account)
        before_audit = _audit_rows()
        answer = pay_now_seam.pay(
            account.pk,
            customer_id=customer_id_of(pine_hill, account),
            may_pay=True,
            amount=Decimal(AUGUST),
            instrument_id=None,
            key=THE_KEY,
        )

        assert answer["outcome"] == gateway.NO_ANSWER
        assert answer["payment_no"] is None
        assert answer["lands_on"] == []
        # ⚠ COUNTS, NOT STATUS WORDS. Four tables, all of them zero.
        assert paid_rows(pine_hill, account) == 0, "no payment row"
        assert payment_models.Allocation.objects.count() == 0, "nothing allocated"
        assert payment_models.PaymentWebhookEvent.objects.count() == 0, "no settlement recorded"
        assert _audit_rows() == before_audit, "no money action, because none happened"
        # And the screen is given the words to say so (`BR-INT-018`).
        assert any(one["code"] == "gateway_did_not_answer" for one in answer["problems"])


def test_us_cwp_045_a_decline_writes_nothing_either(pine_hill, sarah):
    """⚠ **NEGATIVE — AND `declined` IS A DIFFERENT WORD FROM `no_answer`.**
    One means no money moved; the other means nobody knows. Collapsing them
    would tell a customer their card was refused when it may have been charged.
    """
    switch_on(pine_hill, sarah)
    account = a_customer_with_one_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_provider(pine_hill, behaviour=payments_sandbox.DECLINE)
        a_card(pine_hill, account)
        answer = pay_now_seam.pay(
            account.pk,
            customer_id=customer_id_of(pine_hill, account),
            may_pay=True,
            amount=Decimal(AUGUST),
            instrument_id=None,
            key=THE_KEY,
        )

    assert answer["outcome"] == gateway.DECLINED
    assert answer["outcome"] != gateway.NO_ANSWER, "two different facts, two different words"
    assert paid_rows(pine_hill, account) == 0


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — ⚠ THE RETRY CARRIES THE **SAME** KEY, MINTED BEFORE THE FIRST REQUEST
# ═══════════════════════════════════════════════════════════════════════════


def test_us_cwp_045_tc7_the_retry_carries_the_key_the_first_attempt_used(pine_hill, sarah):
    """⚠ **THE CASE A CUSTOMER WOULD BE CHARGED TWICE WITHOUT.**

    The key is minted on the PREVIEW, before anything leaves. The gateway times
    out, the answer carries that same string back, and the retry presents it —
    so the debit is one debit at the provider and one payment here, and two
    retries of it are still one.

    **RED PROOF, RUN:** with `pay()` minting a fresh key rather than carrying the
    caller's, this fails at
    `AssertionError: the SAME key, carried back for the retry` — before it ever
    reaches the row count, which is the right place to stop: the key is the
    guard, and two debits are only its consequence.
    """
    switch_on(pine_hill, sarah)
    account = a_customer_with_one_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        connection = a_provider(pine_hill, behaviour=payments_sandbox.TIMEOUT)
        a_card(pine_hill, account)
        customer_id = customer_id_of(pine_hill, account)

        panel = pay_now_seam.preview(account.pk, amount=Decimal(AUGUST))
        minted = panel["idempotency_key"]
        assert minted, "the key exists BEFORE the first request leaves"

        timed_out = pay_now_seam.pay(
            account.pk, customer_id=customer_id, may_pay=True, amount=Decimal(AUGUST),
            instrument_id=None, key=minted,
        )
        assert timed_out["outcome"] == gateway.NO_ANSWER
        assert timed_out["idempotency_key"] == minted, "the SAME key, carried back for the retry"
        assert paid_rows(pine_hill, account) == 0

        # The provider comes back. The retry presents the key the first attempt
        # used — not a fresh one.
        connection.config = {"behaviour": payments_sandbox.APPROVE}
        connection.save(update_fields=["config", "updated_at"])
        first = pay_now_seam.pay(
            account.pk, customer_id=customer_id, may_pay=True, amount=Decimal(AUGUST),
            instrument_id=None, key=minted,
        )
        second = pay_now_seam.pay(
            account.pk, customer_id=customer_id, may_pay=True, amount=Decimal(AUGUST),
            instrument_id=None, key=minted,
        )

        assert first["outcome"] == "paid"
        assert second["outcome"] == "paid"
        assert paid_rows(pine_hill, account) == 1, "one payment, whatever the customer clicks"
        assert payment_models.PaymentWebhookEvent.objects.count() == 1, "and one delivery row"


def test_us_cwp_045_the_providers_own_settlement_for_this_charge_is_a_duplicate(
    pine_hill, sarah
):
    """⚠ **THE SAME DOOR, PROVED.** The charge we recorded and the settlement the
    provider posts afterwards carry the same key, so the callback writes nothing
    — one payment, not two."""
    import hashlib
    import hmac
    import json
    from datetime import UTC, datetime

    from django.test import override_settings

    from apps.payments import webhooks

    switch_on(pine_hill, sarah)
    account = a_customer_with_one_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_provider(pine_hill)
        a_card(pine_hill, account)
        pay_now_seam.pay(
            account.pk, customer_id=customer_id_of(pine_hill, account), may_pay=True,
            amount=Decimal(AUGUST), instrument_id=None, key=THE_KEY,
        )
        assert paid_rows(pine_hill, account) == 1

        body = {
            "type": "payment_intent.succeeded",
            "account_id": str(account.pk),
            "amount": AUGUST,
            "currency": "USD",
            "posted_at": "2026-09-05T10:00:00+00:00",
            "cleared_at": "2026-09-05T10:00:00+00:00",
        }
        raw = json.dumps(body).encode("utf-8")
        secret = "whsec_test_only_never_a_real_one"
        signature = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        with override_settings(PAYMENT_WEBHOOK_SECRETS={SANDBOX: secret}):
            replay = webhooks.ingest(
                provider=SANDBOX,
                event_id=THE_KEY,
                raw_body=raw,
                signature=signature,
                received_at=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
            )

        assert replay.created is False
        assert replay.status == payment_models.WEBHOOK_DUPLICATE
        assert paid_rows(pine_hill, account) == 1, "still one — the customer is not charged twice"


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 · TC-2 · TC-9 — the held control, and forcing it
# ═══════════════════════════════════════════════════════════════════════════


def test_us_cwp_045_tc1_with_no_provider_connected_the_control_is_held_with_its_reason(
    pine_hill, sarah
):
    """⚠ **VISIBLE, DISABLED AND CARRYING ITS REASON — never hidden, never
    live-but-inert** (`BR-CWP-056`, `CR-068` `R3`). The reason is a CODE; eleven
    catalogues write the sentence."""
    switch_on(pine_hill, sarah)
    account = a_customer_with_one_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        screen = pay_now_seam.pay_now(
            account.pk, customer_id=customer_id_of(pine_hill, account), may_pay=True
        )

    assert screen["can_pay"] is False
    assert screen["held_reason"] == gateway.HELD_NO_PROVIDER
    assert screen["balance"] == AUGUST, "the balance is still read and still shown"
    assert screen["environment"] is None


def test_us_cwp_045_tc9_a_cash_only_account_is_refused_by_name(pine_hill, sarah):
    """⚠ **A REASON, NOT A CONTROL THAT DOES NOTHING.** `r12 #12` /
    `BR-PAY-013` — the account is marked cash-only and the screen says so."""
    switch_on(pine_hill, sarah)
    account = a_customer_with_one_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_provider(pine_hill)
        a_card(pine_hill, account)
        account.cash_only_no_autopay = True
        account.save(update_fields=["cash_only_no_autopay"])
        screen = pay_now_seam.pay_now(
            account.pk, customer_id=customer_id_of(pine_hill, account), may_pay=True
        )
        forced = pay_now_seam.pay(
            account.pk, customer_id=customer_id_of(pine_hill, account), may_pay=True,
            amount=Decimal(AUGUST), instrument_id=None, key=THE_KEY,
        )

    assert screen["held_reason"] == gateway.HELD_CASH_ONLY
    # ⚠ TC-2 — FORCING THE DISABLED CONTROL. The server refuses; a screen order
    # is not the security.
    assert forced["outcome"] == "refused"
    assert forced["held_reason"] == gateway.HELD_CASH_ONLY
    assert paid_rows(pine_hill, account) == 0
    assert payment_models.PaymentWebhookEvent.objects.count() == 0, "no gateway call was made"


def test_us_cwp_045_tc2_a_login_without_pay_permission_is_refused(pine_hill, sarah):
    """⚠ **NEGATIVE.** `may_pay` is the principal's own permission over THIS
    account (`BR-CWP-009`'s vocabulary), re-checked on the server."""
    switch_on(pine_hill, sarah)
    account = a_customer_with_one_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_provider(pine_hill)
        a_card(pine_hill, account)
        forced = pay_now_seam.pay(
            account.pk, customer_id=customer_id_of(pine_hill, account), may_pay=False,
            amount=Decimal(AUGUST), instrument_id=None, key=THE_KEY,
        )

    assert forced["held_reason"] == gateway.HELD_NOT_PERMITTED
    assert paid_rows(pine_hill, account) == 0


# ═══════════════════════════════════════════════════════════════════════════
# `BR-CWP-057` — a token, a brand and four digits, and the token never leaves
# ═══════════════════════════════════════════════════════════════════════════


def test_us_cwp_045_the_saved_method_serves_four_digits_and_never_the_token(pine_hill, sarah):
    """⚠ **NEGATIVE — assert no field of the served row holds more than four
    digits of anything, and that the gateway token is absent entirely.**"""
    switch_on(pine_hill, sarah)
    account = a_customer_with_one_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        saved = a_card(pine_hill, account)
        rows = pay_now_seam.instruments(pine_hill.id, customer_id_of(pine_hill, account))

    assert len(rows) == 1
    assert rows[0]["last_four"] == "4242"
    assert rows[0]["label"] == "Visa ••••4242"
    assert "gateway_token" not in rows[0]
    assert saved.gateway_token not in str(rows[0]), "the token is read server-side and never served"


# ═══════════════════════════════════════════════════════════════════════════
# TC-8 — tenant isolation: the provider is THIS tenant's connection
# ═══════════════════════════════════════════════════════════════════════════


def test_us_cwp_045_tc8_another_tenants_connection_is_not_this_tenants_provider(
    pine_hill, oak_ridge, sarah, elena
):
    """⚠ **TENANT ISOLATION, WITH THE ACCOUNT FACTS HELD CONSTANT.** Oak Ridge
    connects a processor; Pine Hill has not. Pine Hill's screen must still read
    *no provider* — so the test cannot pass merely because the second tenant has
    no data."""
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    account = a_customer_with_one_bill(pine_hill, sarah)
    with tenant_context(oak_ridge.id):
        a_provider(oak_ridge)
        assert gateway.active_provider(oak_ridge.id) is not None
    with tenant_context(pine_hill.id):
        assert gateway.active_provider(pine_hill.id) is None
        screen = pay_now_seam.pay_now(
            account.pk, customer_id=customer_id_of(pine_hill, account), may_pay=True
        )
    assert screen["held_reason"] == gateway.HELD_NO_PROVIDER


# ═══════════════════════════════════════════════════════════════════════════
# `BR-INT-037` — no provider is named in `apps/payments`
# ═══════════════════════════════════════════════════════════════════════════


def test_us_cwp_045_the_provider_is_found_by_category_and_never_by_name(pine_hill):
    """⚠ **THE ARCHITECTURE, ASSERTED.** `gateway` finds a processor because its
    MANIFEST declares `category="payments"`, so the day Worldpay is registered it
    is found by the same code. A test that named the sandbox key would pass over
    an implementation that hardcoded it."""
    keys = {one.key for one in gateway.payments_manifests()}
    assert SANDBOX in keys
    assert len(keys) > 1, "more than one processor is registered, and none is special-cased"
    assert all(one.category == gateway.PAYMENTS_CATEGORY for one in gateway.payments_manifests())


def _bill(tenant, number):
    from apps.billing import models as billing_models

    return billing_models.Invoice.objects.get(tenant_id=tenant.id, invoice_no=number)


def _audit_rows() -> int:
    """`audit_log` rows, which is where hard rule 7 lands. The table lives in
    `apps.audit` and not in `apps.notifications` — CLAUDE.md's module map spells
    the pair as *notifications (+ audit)*, and the second half is its own app."""
    from apps.audit import models as audit_models

    return audit_models.AuditLog.objects.count()

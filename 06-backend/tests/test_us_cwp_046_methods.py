# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-046 (EP-CWP-09) — your payment methods. Screen: CWP-039
# Rules:    BR-CWP-057 (a token with a brand and a last four; the product never
#           holds a full card number) · BR-CWP-010 (tenant AND the login's own
#           set, intersected IN THE QUERY) · BR-CWP-056 (a refused control is
#           visible, disabled and carries its reason — never hidden, never
#           live-but-inert) · BR-PAY-013 (the cash-only / no-autopay privilege
#           flag and the bounce count) · CLAUDE.md hard rule 1 · rule 7
# Tests:    this file
# Impacts:  apps/payments/instruments.py · apps/portal/api.py
# ───────────────────────────────────────────────────────
"""`US-CWP-046`'s cases — and the one the whole screen rests on is TC-2.

⚠ **THE PRODUCT NEVER HOLDS A CARD NUMBER** (`BR-CWP-057`). Every other case
here is a list, a status or a refusal; TC-2 is the compliance surface. It is
asserted in three places rather than one, because each catches a different way
of losing it:

  * **the wire** — the served row's keys are a closed set and `gateway_token`
    is not among them, so a serialiser that grew a field cannot leak the token;
  * **the row** — `last_four` is four digits and the model has no column a
    longer number would fit in;
  * **the door** — `save_instrument` REFUSES a reference carrying a PAN-shaped
    digit run. That one exists because the first two are guarantees about what
    we store, and the way a card number actually arrives is somebody posting
    one into the field meant for the gateway's reference.

⚠ **TC-9 IS AMENDED AND THE AMENDMENT IS THE POINT.** The story text says a
card-fee computation raises `NotImplementedError("OQ-1394")`. `OQ-1394` was
**CLOSED on 2026-09-04** — both absorb and surcharge, behind a per-tenant
switch — so citing it as a blocker would be the re-ask hard-won law 13 forbids,
one layer down. The refusal STANDS and its reason changed: the switch stores
the utility's *intention*, and there is no processor and therefore no fee
schedule to compute a surcharge FROM. `settings_families.py` says exactly that
beside the `card_fee_payer` parameter: *"apps/payments REFUSES to price a
surcharge by name rather than inventing a percentage"*. This file is where that
refusal is asserted.

⚠ **TC-8 (a delegate with See only) IS NOT BUILT AND THAT IS A RULING**
(`OQ-1396`, CLOSED 2026-09-04: *"we are not giveing this acces as of now"*).
Delegate access is DEFERRED, `session._delegated()` returns empty, and there is
no way to construct the delegate this case needs. The absence is asserted below
rather than skipped, so the day delegates ship the assertion fails and names
this case.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import pytest
from django.test import Client

from apps.customers import models as customers_models
from apps.payments import models as payment_models
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    elm_street_account,
    enrol_maria,
    switch_on,
)

#: The two methods `US-CWP-046` §4 names, verbatim.
CHASE = {"brand": "Chase", "last_four": "4021", "kind": "bank"}
VISA = {"brand": "Visa", "last_four": "8812", "kind": "card"}

#: A run of five or more digits. `BR-CWP-057`'s guard, and the same expression
#: the service uses — a card number is the only thing on this screen that could
#: produce one.
PAN_SHAPED = re.compile(r"\d{5,}")


def portal_url(tenant, path: str) -> str:
    return f"/api/{tenant.subdomain}/portal/{path}"


def signed_in(tenant):
    client = Client()
    answer = client.post(
        portal_url(tenant, "auth/sign-in"),
        data=json.dumps({"email": MARIA_EMAIL, "password": MARIA_PASSWORD}),
        content_type="application/json",
    )
    assert answer.status_code == 200, answer.content
    return client


def post(client, tenant, path: str, body: dict):
    return client.post(
        portal_url(tenant, path), data=json.dumps(body), content_type="application/json"
    )


def maria_signed_in(tenant, actor):
    """The portal live, Maria enrolled, and her account on file."""
    switch_on(tenant, actor)
    account = elm_street_account(tenant, actor)
    credential = enrol_maria(tenant, actor)
    return signed_in(tenant), credential, account


def an_instrument(tenant, customer_id, spec, *, added_on=None, expires=None, used_for=None,
                  status=None):
    """One `stored_payment_instruments` row, written through the ORM.

    The DOOR is `save_instrument` and `US-CWP-022` TC-1 exercises it. What this
    story is about is the READ over rows that already exist, so the fixture
    writes them directly — the same posture `test_us_cwp_helpers.an_issued_bill`
    states for bills.
    """
    with tenant_context(tenant.id):
        row = payment_models.StoredPaymentInstrument.objects.create(
            tenant_id=tenant.id,
            customer_id=customer_id,
            gateway_token=f"tok_test_{spec['brand'].lower()}_{spec['last_four']}",
            brand=spec["brand"],
            last_four=spec["last_four"],
            kind=spec["kind"],
            status=status
            or (
                payment_models.INSTRUMENT_VERIFIED
                if spec["kind"] == payment_models.INSTRUMENT_BANK
                else payment_models.INSTRUMENT_ACTIVE
            ),
            used_for=list(used_for or [payment_models.INSTRUMENT_USE_ONE_OFF]),
            expires_month=(expires or (None, None))[0],
            expires_year=(expires or (None, None))[1],
        )
        if added_on is not None:
            payment_models.StoredPaymentInstrument.objects.filter(pk=row.pk).update(
                created_at=added_on
            )
        return row


def two_saved_methods(tenant, credential):
    """`US-CWP-046` §4's test data: Chase ••••4021 and Visa ••••8812."""
    an_instrument(
        tenant,
        credential.customer_id,
        CHASE,
        added_on=datetime(2026, 3, 4, 9, 0, tzinfo=UTC),
        used_for=[payment_models.INSTRUMENT_USE_AUTOPAY, payment_models.INSTRUMENT_USE_ONE_OFF],
    )
    an_instrument(
        tenant,
        credential.customer_id,
        VISA,
        added_on=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
        expires=(11, 2027),
        used_for=[payment_models.INSTRUMENT_USE_ONE_OFF],
    )


def methods_of(body):
    return {row["last_four"]: row for row in body["methods"]}


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the two saved methods, exactly as §4 names them
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc1__two_saved_methods_read_back_with_their_brand_and_four_digits(pine_hill, sarah):
    client, credential, _account = maria_signed_in(pine_hill, sarah)
    two_saved_methods(pine_hill, credential)

    answer = client.get(portal_url(pine_hill, "payment-methods"))
    assert answer.status_code == 200, answer.content
    rows = methods_of(answer.json())

    assert set(rows) == {"4021", "8812"}
    chase = rows["4021"]
    assert chase["brand"] == "Chase"
    assert chase["kind"] == "bank"
    assert chase["status"] == "verified"
    assert chase["used_for"] == ["autopay", "one_off"]
    assert chase["expires"] is None  # a mandate has no expiry
    assert chase["added_on"] == "2026-03-04"

    visa = rows["8812"]
    assert visa["brand"] == "Visa"
    assert visa["kind"] == "card"
    assert visa["status"] == "active"
    assert visa["expires"] == "11/27"
    assert visa["usable"] is True


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — a token, a brand and four digits, and NOTHING ELSE (BR-CWP-057)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc2__the_served_row_carries_no_token_and_no_digits_beyond_four(pine_hill, sarah):
    client, credential, _account = maria_signed_in(pine_hill, sarah)
    two_saved_methods(pine_hill, credential)

    body = client.get(portal_url(pine_hill, "payment-methods")).json()
    for row in body["methods"]:
        # ⚠ A CLOSED SET. A serialiser that grew a field would fail here rather
        # than shipping whatever the model gained.
        assert set(row) == {
            "ref",
            "brand",
            "last_four",
            "kind",
            "status",
            "used_for",
            "added_on",
            "expires",
            "usable",
        }
        assert "gateway_token" not in row
        assert len(row["last_four"]) == 4 and row["last_four"].isdigit()
        # ⚠ `ref` is excluded DELIBERATELY: it is a row id in a URL, never a
        # value on screen (B14 rule 31, asserted in Methods.dom.test.tsx), and
        # a uuid's hex can hold a five-digit run by chance.
        scanned = {key: value for key, value in row.items() if key != "ref"}
        assert not PAN_SHAPED.search(json.dumps(scanned)), scanned


@pytest.mark.django_db
def test_tc2__the_stored_row_holds_four_digits_and_the_column_cannot_hold_more(pine_hill, sarah):
    _client, credential, _account = maria_signed_in(pine_hill, sarah)
    two_saved_methods(pine_hill, credential)

    with tenant_context(pine_hill.id):
        for row in payment_models.StoredPaymentInstrument.objects.all():
            assert len(row.last_four) == 4
    # The guarantee is the COLUMN, not a rule saying not to put one there.
    field = payment_models.StoredPaymentInstrument._meta.get_field("last_four")
    assert field.max_length == 4


@pytest.mark.django_db
def test_tc2__the_door_refuses_a_reference_that_looks_like_a_card_number(pine_hill, sarah):
    """⚠ **THE WAY A CARD NUMBER ACTUALLY ARRIVES.** Not through a column — there
    is none — but through somebody posting a PAN into the field meant for the
    gateway's reference. Refused, and nothing is written."""
    from apps.payments import instruments

    _client, credential, _account = maria_signed_in(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        with pytest.raises(instruments.LooksLikeACardNumber):
            instruments.save_instrument(
                None,
                tenant_id=pine_hill.id,
                customer_id=credential.customer_id,
                reference="4111111111111111",
            )
        assert not payment_models.StoredPaymentInstrument.objects.exists()


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — adding without a fresh code is refused (US-CWP-022 does the detail)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc3__adding_a_method_without_a_fresh_code_is_refused(pine_hill, sarah):
    client, _credential, _account = maria_signed_in(pine_hill, sarah)
    answer = post(client, pine_hill, "payment-methods", {"reference": "card-page-ref-1"})
    assert answer.status_code == 400, answer.content
    assert answer.json()["saved"] is False
    with tenant_context(pine_hill.id):
        assert not payment_models.StoredPaymentInstrument.objects.exists()


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 / TC-5 — a refused control is VISIBLE, DISABLED and CARRIES ITS REASON
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc4__a_cash_only_account_refuses_autopay_and_says_why(pine_hill, sarah):
    client, credential, account = maria_signed_in(pine_hill, sarah)
    two_saved_methods(pine_hill, credential)
    with tenant_context(pine_hill.id):
        customers_models.Account.objects.filter(pk=account.pk).update(cash_only_no_autopay=True)

    body = client.get(portal_url(pine_hill, "payment-methods")).json()
    assert body["autopay"]["allowed"] is False
    assert body["autopay"]["reason"] == "cash_only"
    # ⚠ AND THE METHODS ARE STILL THERE. BR-CWP-056 — the control is disabled
    # with its reason, never removed, and the list it sits over is untouched.
    assert len(body["methods"]) == 2


@pytest.mark.django_db
def test_tc5__two_bounces_name_the_bounces_and_the_control_is_disabled_not_absent(
    pine_hill, sarah
):
    client, credential, account = maria_signed_in(pine_hill, sarah)
    two_saved_methods(pine_hill, credential)
    with tenant_context(pine_hill.id):
        customers_models.Account.objects.filter(pk=account.pk).update(nsf_count=2)

    body = client.get(portal_url(pine_hill, "payment-methods")).json()
    assert body["autopay"]["allowed"] is False
    assert body["autopay"]["reason"] == "bounced"
    assert body["autopay"]["bounces"] == 2
    assert len(body["methods"]) == 2


@pytest.mark.django_db
def test_an_account_with_neither_block_may_use_autopay(pine_hill, sarah):
    client, credential, _account = maria_signed_in(pine_hill, sarah)
    two_saved_methods(pine_hill, credential)
    body = client.get(portal_url(pine_hill, "payment-methods")).json()
    assert body["autopay"] == {"allowed": True, "reason": None, "bounces": 0}


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — an expired card reads expired and cannot be chosen for a payment
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc6__an_expired_card_reads_expired_and_is_not_selectable(pine_hill, sarah):
    client, credential, _account = maria_signed_in(pine_hill, sarah)
    an_instrument(
        pine_hill,
        credential.customer_id,
        {"brand": "Visa", "last_four": "4417", "kind": "card"},
        expires=(8, 2026),
    )
    body = client.get(portal_url(pine_hill, "payment-methods")).json()
    row = methods_of(body)["4417"]
    # ⚠ DERIVED, NOT STORED. The row was written `active`; nothing runs
    # nightly to age it, so a read that trusted the column would offer an
    # expired card for a payment for as long as nobody swept the table.
    assert row["status"] == "expired"
    assert row["usable"] is False
    assert row["expires"] == "08/26"


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — tenant isolation, and the OTHER half of BR-CWP-010
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc7__another_tenants_methods_are_invisible(pine_hill, sarah, oak_ridge, elena):
    client, credential, _account = maria_signed_in(pine_hill, sarah)
    two_saved_methods(pine_hill, credential)
    with tenant_context(oak_ridge.id):
        stranger = customers_models.Customer.objects.create(
            tenant_id=oak_ridge.id, display_name="Oak Ridge Holdings"
        )
    an_instrument(oak_ridge, stranger.pk, {"brand": "Amex", "last_four": "9931", "kind": "card"},
                  expires=(4, 2029))

    body = client.get(portal_url(pine_hill, "payment-methods")).json()
    assert set(methods_of(body)) == {"4021", "8812"}


@pytest.mark.django_db
def test_tc7__another_customer_of_the_same_utility_is_invisible_too(pine_hill, sarah):
    """`BR-CWP-010`'s second half. Same tenant, different customer — and the
    intersection is in the QUERY, so this is not a screen that filters."""
    client, credential, _account = maria_signed_in(pine_hill, sarah)
    two_saved_methods(pine_hill, credential)
    with tenant_context(pine_hill.id):
        neighbour = customers_models.Customer.objects.create(
            tenant_id=pine_hill.id, display_name="Someone Else"
        )
    an_instrument(pine_hill, neighbour.pk, {"brand": "Visa", "last_four": "1122", "kind": "card"},
                  expires=(1, 2030))

    body = client.get(portal_url(pine_hill, "payment-methods")).json()
    assert set(methods_of(body)) == {"4021", "8812"}


# ═══════════════════════════════════════════════════════════════════════════
# TC-8 — DEFERRED BY RULING, and the absence is asserted (OQ-1396)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc8__there_is_no_delegate_to_refuse_because_delegate_access_is_deferred(
    pine_hill, sarah
):
    """⚠ **`OQ-1396` CLOSED 2026-09-04 — the FEATURE is deferred**, so there is
    no delegate to hold *See only* and TC-8 has nothing to construct. This
    asserts the deliberate absence: the day `_delegated` returns a row, this
    fails and names the case that has to be written."""
    from apps.portal import session as portal_session

    _client, credential, _account = maria_signed_in(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        assert portal_session._delegated(pine_hill.id, credential.pk) == []


# ═══════════════════════════════════════════════════════════════════════════
# TC-9 (AMENDED) — the surcharge is not priced, and it refuses BY NAME
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc9__the_card_fee_stance_is_read_from_the_tenant_switch_not_invented(pine_hill, sarah):
    client, _credential, _account = maria_signed_in(pine_hill, sarah)
    body = client.get(portal_url(pine_hill, "payment-methods")).json()
    # The seeded default is `utility` and that default IS the safety argument
    # (hard-won law 3): surcharging is regulated in several states.
    assert body["card_fee"] == {"payer": "utility", "priced": False, "reason": "no_processor"}


@pytest.mark.django_db
def test_tc9__asking_for_a_surcharge_figure_refuses_rather_than_inventing_one(pine_hill, sarah):
    from apps.payments import instruments

    maria_signed_in(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        with pytest.raises(instruments.SurchargeNotPriced) as raised:
            instruments.price_card_surcharge("142.1800")
    # ⚠ The message names the MISSING THING, never a closed question. OQ-1394
    # is CLOSED; what does not exist is a processor's fee schedule.
    assert "processor" in str(raised.value)
    assert "OQ-1394" not in str(raised.value)

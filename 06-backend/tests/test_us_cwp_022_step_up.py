# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-022 (EP-CWP-05) — step up before a stored method changes.
#           Screen: CWP-039
# Rules:    BR-CWP-040 (a second factor at enrolment AND step-up before a
#           payment method is added, changed or removed) · BR-CWP-035 (ten
#           minutes, single use) · BR-CWP-057 (there is no card number to
#           protect; the DESTINATION OF MONEY is what is being protected) ·
#           BR-CWP-010 · CLAUDE.md hard rule 7 (every money action is audited)
# Tests:    this file
# Impacts:  apps/portal/api.py (`payment_methods`, `payment_method_step_up`,
#           `payment_method_remove`) · apps/payments/instruments.py ·
#           apps/portal/models.py (`PURPOSE_STEP_UP` — the fourth door)
# ───────────────────────────────────────────────────────
"""`US-CWP-022` — and TC-3 is the case the whole story exists for.

⚠ **STEP-UP NEEDS ITS OWN CODE, NOT THE SESSION'S.** A code that got somebody
IN must not also let them redirect where their money goes: the two are minutes
apart in a hijacked session, which is the exact window `BR-CWP-040` closes. The
mechanism is the `purpose` column — `verify_code` filters on it, so an
enrolment code presented at this door does not match a row and is refused
without any check having to remember to look.

⚠ **THE DELEGATE CASES (TC-5, TC-7) ARE NOT BUILT AND THAT IS A RULING.**
`OQ-1396` CLOSED 2026-09-04 — *"we are not giveing this acces as of now"* —
so delegate access is DEFERRED and there is no delegate to act. What survives
of TC-7 is the half that is real today: the audit entry names WHOEVER acted,
carried in the payload rather than in `actor_user_id`, because a portal
customer is not a `User` (`BR-CWP-004`). That is asserted in TC-1.
"""

from __future__ import annotations

import json

import pytest
from django.test import Client
from django.utils import timezone

from apps.payments import models as payment_models
from apps.portal import credentials, models as portal_models
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    elm_street_account,
    enrol_maria,
    switch_on,
)

#: What a real card page hands back — a reference to the tokenisation, never a
#: card number (`BR-CWP-057`). The sandbox provider turns it into a token.
CARD_PAGE_REFERENCE = "cardpage-9f2a-visa"


def portal_url(tenant, path: str) -> str:
    return f"/api/{tenant.subdomain}/portal/{path}"


def signed_in(tenant, *, email=MARIA_EMAIL, password=MARIA_PASSWORD):
    client = Client()
    answer = client.post(
        portal_url(tenant, "auth/sign-in"),
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json",
    )
    assert answer.status_code == 200, answer.content
    return client


def post(client, tenant, path: str, body: dict):
    return client.post(
        portal_url(tenant, path), data=json.dumps(body), content_type="application/json"
    )


def maria_signed_in(tenant, actor):
    switch_on(tenant, actor)
    account = elm_street_account(tenant, actor)
    credential = enrol_maria(tenant, actor)
    return signed_in(tenant), credential, account


def live_step_up_code(tenant, credential):
    """The code that was just issued, read back off its row's own hash source.

    ⚠ **THE CODE ITSELF IS NEVER STORED** (`PortalOneTimeCode`'s docstring), so
    a test cannot read it out of the table. It comes off the queued outbound
    row, which is where `US-CWP-017`'s test reads it from and is the only place
    it was ever meant to exist.
    """
    from apps.notifications import models as notification_models

    with tenant_context(tenant.id):
        row = (
            portal_models.PortalOneTimeCode.objects.filter(
                tenant_id=tenant.id,
                purpose=portal_models.PURPOSE_STEP_UP,
                portal_credential_id=credential.pk,
                consumed_at__isnull=True,
                superseded_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )
        assert row is not None, "no live step-up code was issued"
        message = notification_models.OutboundMessage.objects.filter(
            tenant_id=tenant.id, pk=row.outbound_message_id
        ).first()
        assert message is not None, "the code was issued and never queued"
        return str(message.render_context["code"])


def a_saved_card(tenant, customer_id):
    with tenant_context(tenant.id):
        return payment_models.StoredPaymentInstrument.objects.create(
            tenant_id=tenant.id,
            customer_id=customer_id,
            gateway_token="tok_test_existing_8812",
            brand="Visa",
            last_four="8812",
            kind=payment_models.INSTRUMENT_CARD,
            status=payment_models.INSTRUMENT_ACTIVE,
            expires_month=11,
            expires_year=2027,
            used_for=[payment_models.INSTRUMENT_USE_ONE_OFF],
        )


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — a fresh code adds the method, and the audit entry names the actor
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc1__a_fresh_code_saves_the_method_and_the_trail_names_who_did_it(
    pine_hill, sarah, audit_rows
):
    client, credential, _account = maria_signed_in(pine_hill, sarah)

    asked = post(client, pine_hill, "payment-methods/step-up", {})
    assert asked.status_code == 200, asked.content
    assert asked.json()["expires_in_minutes"] == portal_models.CODE_TTL_MINUTES
    # ⚠ THE MASKED DESTINATION AND NOTHING MORE. A step-up response that named
    # the contact would hand a hijacked session the address to intercept.
    assert asked.json()["sent_to"].startswith("•")

    code = live_step_up_code(pine_hill, credential)
    saved = post(
        client,
        pine_hill,
        "payment-methods",
        {"code": code, "reference": CARD_PAGE_REFERENCE},
    )
    assert saved.status_code == 201, saved.content
    assert saved.json()["saved"] is True

    with tenant_context(pine_hill.id):
        rows = list(payment_models.StoredPaymentInstrument.objects.all())
    assert len(rows) == 1
    # The sandbox provider's conspicuous token and four digits — see its own
    # docstring for why they are obviously fake.
    assert rows[0].gateway_token.startswith("tok_test_")
    assert rows[0].last_four == "4242"
    assert rows[0].customer_id == credential.customer_id

    # Hard rule 7. `actor_user_id` stays NULL — a portal customer is not a
    # `User` (`BR-CWP-004`) — and the payload names them and their session.
    written = [row for row in audit_rows if row["action"] == "portal.payment_method.added"]
    assert written, [row["action"] for row in audit_rows]
    actor = written[-1]["after"]["actor"]
    assert written[-1]["actor_user_id"] is None
    assert actor["portal_customer_id"] == str(credential.customer_id)
    assert actor["channel"] == "customer_portal"
    assert actor["portal_session_id"]


@pytest.mark.django_db
def test_tc1__the_code_is_single_use_so_a_second_method_needs_a_second_code(
    pine_hill, sarah
):
    """`BR-CWP-035` — single use. Replaying the code that added one card must
    not add a second, or step-up is a formality the first time only."""
    client, credential, _account = maria_signed_in(pine_hill, sarah)
    post(client, pine_hill, "payment-methods/step-up", {})
    code = live_step_up_code(pine_hill, credential)

    first = post(client, pine_hill, "payment-methods", {"code": code, "reference": "ref-one"})
    assert first.status_code == 201, first.content
    again = post(client, pine_hill, "payment-methods", {"code": code, "reference": "ref-two"})
    assert again.status_code == 400, again.content
    with tenant_context(pine_hill.id):
        assert payment_models.StoredPaymentInstrument.objects.count() == 1


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — no code at all
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc2__adding_a_method_with_no_code_is_refused_at_the_endpoint(pine_hill, sarah):
    """⚠ **AT THE ENDPOINT, NOT IN THE WIZARD** — the same posture
    `set-password` takes (`US-CWP-019` TC-4). A screen order is not security."""
    client, _credential, _account = maria_signed_in(pine_hill, sarah)
    answer = post(client, pine_hill, "payment-methods", {"reference": CARD_PAGE_REFERENCE})
    assert answer.status_code == 400, answer.content
    assert answer.json() == {"saved": False, "reason": "code_needed"}
    with tenant_context(pine_hill.id):
        assert not payment_models.StoredPaymentInstrument.objects.exists()


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — THE CASE THE STORY EXISTS FOR: the sign-in code will not do
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc3__an_enrolment_code_from_ten_minutes_ago_is_refused_here(pine_hill, sarah):
    client, credential, account = maria_signed_in(pine_hill, sarah)

    # A perfectly good enrolment code, live and unconsumed — the one that got
    # this person in. It is the WRONG DOOR and that is the whole guard.
    with tenant_context(pine_hill.id):
        issued = credentials.issue_code(
            pine_hill.id,
            purpose=portal_models.PURPOSE_ENROL,
            account=account,
            channel=portal_models.CHANNEL_SMS,
            masked="••• ••• 0144",
        )

    answer = post(
        client,
        pine_hill,
        "payment-methods",
        {"code": issued.code, "reference": CARD_PAGE_REFERENCE},
    )
    assert answer.status_code == 400, answer.content
    assert answer.json()["reason"] == credentials.CODE_WRONG
    with tenant_context(pine_hill.id):
        assert not payment_models.StoredPaymentInstrument.objects.exists()
        # ⚠ AND THE ENROLMENT CODE IS STILL LIVE. Refusing it here must not
        # burn it: a code presented at the wrong door is not an attempt on the
        # right one, and consuming it would log the customer out of the flow
        # that actually owns it.
        still = portal_models.PortalOneTimeCode.objects.get(pk=issued.row_id)
        assert still.consumed_at is None
        assert still.attempts == 0


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — removing with an expired code
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc4__removing_a_method_with_an_expired_code_is_refused(pine_hill, sarah):
    client, credential, _account = maria_signed_in(pine_hill, sarah)
    card = a_saved_card(pine_hill, credential.customer_id)

    post(client, pine_hill, "payment-methods/step-up", {})
    code = live_step_up_code(pine_hill, credential)
    with tenant_context(pine_hill.id):
        portal_models.PortalOneTimeCode.objects.filter(
            tenant_id=pine_hill.id, purpose=portal_models.PURPOSE_STEP_UP
        ).update(expires_at=timezone.now() - timezone.timedelta(minutes=1))

    answer = post(client, pine_hill, f"payment-methods/{card.pk}/remove", {"code": code})
    assert answer.status_code == 400, answer.content
    assert answer.json()["reason"] == credentials.CODE_EXPIRED
    with tenant_context(pine_hill.id):
        assert payment_models.StoredPaymentInstrument.objects.get(pk=card.pk).deleted_at is None


@pytest.mark.django_db
def test_a_fresh_code_removes_it_softly_and_the_trail_names_who(pine_hill, sarah, audit_rows):
    """The positive half of TC-4 — and the removal is SOFT, because a payment
    already taken on this instrument names it and hard rule 4 forbids
    destroying what a payment points at."""
    client, credential, _account = maria_signed_in(pine_hill, sarah)
    card = a_saved_card(pine_hill, credential.customer_id)

    post(client, pine_hill, "payment-methods/step-up", {})
    code = live_step_up_code(pine_hill, credential)
    answer = post(client, pine_hill, f"payment-methods/{card.pk}/remove", {"code": code})
    assert answer.status_code == 200, answer.content
    assert answer.json()["removed"] is True

    with tenant_context(pine_hill.id):
        row = payment_models.StoredPaymentInstrument.objects.get(pk=card.pk)
        assert row.deleted_at is not None
    assert client.get(portal_url(pine_hill, "payment-methods")).json()["methods"] == []
    assert [one for one in audit_rows if one["action"] == "portal.payment_method.removed"]


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — a code issued on one utility is refused on another
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc6__a_pine_hill_code_used_on_oak_ridge_is_refused(pine_hill, sarah, oak_ridge, elena):
    """⚠ **TWO SEPARATE RELATIONSHIPS, TWO SEPARATE PASSWORDS** — a credential
    is unique per tenant, so a Pine Hill session simply is not signed in at Oak
    Ridge. The step-up code cannot be carried across because the SESSION cannot
    be: the refusal is the door, one layer before the code is even read."""
    client, credential, _account = maria_signed_in(pine_hill, sarah)
    post(client, pine_hill, "payment-methods/step-up", {})
    code = live_step_up_code(pine_hill, credential)
    switch_on(oak_ridge, elena)

    answer = post(
        client, oak_ridge, "payment-methods", {"code": code, "reference": CARD_PAGE_REFERENCE}
    )
    # ⚠ **404, AND THAT IS THE RIGHT ANSWER RATHER THAN A WEAKER ONE.** A
    # session that is not this utility's is not admitted at all, so the edge
    # does not confirm that the route exists — the same posture every
    # account-scoped read on this edge takes (`BR-CWP-010`). The point of the
    # case is that the code is never even read; whether the refusal is
    # 401, 403 or 404 is the door's business.
    assert answer.status_code in (401, 403, 404), answer.content
    with tenant_context(oak_ridge.id):
        assert not payment_models.StoredPaymentInstrument.objects.exists()


@pytest.mark.django_db
def test_tc6__and_the_code_row_itself_is_scoped_to_the_utility_that_issued_it(
    pine_hill, sarah, oak_ridge, elena
):
    """The layer under the session. Even holding the code and a credential id,
    `verify_code` filters on `tenant_id` IN THE QUERY (hard rule 1)."""
    _client, credential, _account = maria_signed_in(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        issued = credentials.issue_code(
            pine_hill.id,
            purpose=portal_models.PURPOSE_STEP_UP,
            credential=credential,
            channel=portal_models.CHANNEL_SMS,
            masked="••• ••• 0144",
        )
    with tenant_context(oak_ridge.id):
        verdict = credentials.verify_code(
            oak_ridge.id,
            purpose=portal_models.PURPOSE_STEP_UP,
            code=issued.code,
            credential=credential,
        )
    assert verdict == credentials.CODE_WRONG


# ═══════════════════════════════════════════════════════════════════════════
# BR-CWP-010 — a method belonging to somebody else cannot be removed
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_removing_another_customers_method_answers_the_same_404_as_one_that_does_not_exist(
    pine_hill, sarah
):
    """⚠ **THE SAME BODY BOTH TIMES**, so the id space cannot be walked to find
    out which instruments exist — the posture `_account_in_set` already takes
    for accounts."""
    from apps.customers import models as customers_models

    client, credential, _account = maria_signed_in(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        neighbour = customers_models.Customer.objects.create(
            tenant_id=pine_hill.id, display_name="Someone Else"
        )
    theirs = a_saved_card(pine_hill, neighbour.pk)

    def with_a_fresh_code(ref: str):
        """⚠ **A SECOND CODE, BECAUSE THE FIRST ONE IS SPENT** (`BR-CWP-035`).
        The step-up is proved BEFORE the instrument is looked up, so a removal
        that then fails still consumes the code — which is the safe direction
        (an attempt was made) and is why this case cannot reuse one code twice."""
        post(client, pine_hill, "payment-methods/step-up", {})
        return post(
            client,
            pine_hill,
            f"payment-methods/{ref}/remove",
            {"code": live_step_up_code(pine_hill, credential)},
        )

    answer = with_a_fresh_code(str(theirs.pk))
    assert answer.status_code == 404, answer.content
    nowhere = with_a_fresh_code("0198f0aa-0000-7000-8000-00000000dead")
    assert nowhere.status_code == 404, nowhere.content

    # The SAME body both times, so the two cases cannot be told apart.
    # ⚠ `trace_id` is dropped and only that: it is a per-REQUEST correlation id
    # that differs on two identical calls, so comparing it would make this
    # assertion always fail and prove nothing about disclosure.
    def without_trace(response):
        return {key: value for key, value in response.json().items() if key != "trace_id"}

    assert without_trace(answer) == without_trace(nowhere)
    with tenant_context(pine_hill.id):
        assert payment_models.StoredPaymentInstrument.objects.get(pk=theirs.pk).deleted_at is None

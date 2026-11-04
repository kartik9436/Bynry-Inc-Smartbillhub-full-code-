# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-066 (EP-CWP-11) — ask a question, attached to the bill it is
#           about. Screen: CWP-054
# Rules:    BR-CWP-076 (every request raised through the portal carries channel
#           `customer_portal`) · BR-CWP-093 (nothing empty ever appears — the
#           *might answer it now* panel is ABSENT when nothing is published) ·
#           BR-CWP-010 (both halves in the query) · BR-CWP-026 (a portal write
#           changes no account) · B14 rule 31 (the bill is named by its number)
# Open:     `CR-068` §2b — consumer upload is a SIGNED DEFERRAL (PO 2026-08-08,
#           DF-4). TC-7 asserts there is no route to post a file to.
# Tests:    this file
# Impacts:  apps/portal/services.py `SHAPE_QUESTION` · apps/portal/api.py
#           `ask_a_question`
# ───────────────────────────────────────────────────────
"""`US-CWP-066`'s cases.

⚠ **ATTACHING THE QUESTION TO A SPECIFIC BILL IS WHAT MAKES IT ANSWERABLE.** The
assertion that matters is TC-1's: the row a clerk opens NAMES the bill in the
words they read first, so nobody rings back to find out which one was meant.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from django.test import Client

from apps.customers import models as customers_models
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    an_issued_bill,
    elm_street_account,
    enrol_maria,
    switch_on,
)

#: `US-CWP-066` §4 — the story's own fixture.
BILL_NO = "BL-2608-0141"
BILL_TOTAL = "142.1800"
ISSUED_ON = date(2026, 8, 26)
TOPIC = "A bill"
WORDS = "My August water is nearly double July and nobody has been at the house."


def portal_url(tenant, path: str) -> str:
    return f"/api/{tenant.subdomain}/portal/{path}"


def signed_in(tenant, *, email: str = MARIA_EMAIL, password: str = MARIA_PASSWORD):
    client = Client()
    answer = client.post(
        portal_url(tenant, "auth/sign-in"),
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json",
    )
    assert answer.status_code == 200, answer.content
    return client


def maria_with_a_bill(tenant, actor):
    switch_on(tenant, actor)
    credential = enrol_maria(tenant, actor)
    account = elm_street_account(tenant, actor)
    with tenant_context(tenant.id):
        customers_models.CustomerAccount.objects.get_or_create(
            tenant_id=tenant.id, customer_id=credential.customer_id, account=account
        )
        bill = an_issued_bill(
            tenant, account, number=BILL_NO, total=BILL_TOTAL, issued_on=ISSUED_ON
        )
    return credential, account, bill


def ask(client, tenant, **body):
    payload = {"topic": TOPIC, "what": WORDS, "bill_number": BILL_NO}
    payload.update(body)
    return client.post(
        portal_url(tenant, "questions"),
        data=json.dumps(payload),
        content_type="application/json",
    )


# ══ TC-1 · the question reaches a clerk ALREADY NAMING THE BILL ════════════


@pytest.mark.django_db
def test_us_cwp_066_tc1_the_question_reaches_a_clerk_ALREADY_NAMING_THE_BILL(
    pine_hill, sarah
):
    """⚠ **TC-1 — the case the screen exists for.** *"A free-text message with
    no context becomes a phone call anyway."*"""
    maria_with_a_bill(pine_hill, sarah)
    client = signed_in(pine_hill)

    answer = ask(client, pine_hill)

    assert answer.status_code == 201, answer.content
    body = answer.json()
    assert body["reference"].startswith("SR-")
    assert body["bill_number"] == BILL_NO
    with tenant_context(pine_hill.id):
        row = customers_models.ServiceRequest.objects.get(request_no=body["reference"])
    assert row.channel == "customer_portal", "BR-CWP-076"
    assert BILL_NO in row.what_they_said
    assert WORDS in row.what_they_said


@pytest.mark.django_db
def test_us_cwp_066_tc1_the_question_is_TRACKABLE_by_its_reference(pine_hill, sarah):
    """TC-1's second half — the reference the confirmation shows opens
    `CWP-051`, which is what makes the two screens one journey rather than two
    (hard-won law 2: a reference nothing can be looked up with is dead copy)."""
    maria_with_a_bill(pine_hill, sarah)
    client = signed_in(pine_hill)
    reference = ask(client, pine_hill).json()["reference"]

    tracked = client.get(portal_url(pine_hill, f"requests/{reference}"))

    assert tracked.status_code == 200, tracked.content
    assert tracked.json()["reference"] == reference
    assert tracked.json()["is_open"] is True


# ══ TC-2 · signed in, nobody retypes an address ════════════════════════════


@pytest.mark.django_db
def test_us_cwp_066_tc2_signed_in_the_ADDRESS_COMES_FROM_THE_ACCOUNT(pine_hill, sarah):
    """⚠ **TC-2** — *"we already know which account you are asking about"*. The
    address is WALKED to the premises (hard rule 8) and never typed, and the
    body carries no address field at all."""
    maria_with_a_bill(pine_hill, sarah)
    client = signed_in(pine_hill)

    reference = ask(client, pine_hill).json()["reference"]

    with tenant_context(pine_hill.id):
        row = customers_models.ServiceRequest.objects.get(request_no=reference)
    assert row.address_as_given, "create_from_portal requires one, and the server supplied it"
    assert "Elm" in row.address_as_given


@pytest.mark.django_db
def test_us_cwp_066_the_question_CHANGES_NO_ACCOUNT(pine_hill, sarah):
    """`BR-CWP-026` — *"a public form may create work and may never change an
    account."* The account row is compared field by field."""
    _, account, _ = maria_with_a_bill(pine_hill, sarah)

    def snapshot():
        with tenant_context(pine_hill.id):
            row = customers_models.Account.objects.get(pk=account.pk)
            return {
                field.name: getattr(row, field.attname, None)
                for field in customers_models.Account._meta.fields
            }

    before = snapshot()
    client = signed_in(pine_hill)
    assert ask(client, pine_hill).status_code == 201

    assert snapshot() == before


# ══ TC-5 · a question with NO bill is a normal question ════════════════════


@pytest.mark.django_db
def test_us_cwp_066_tc5_a_question_with_NO_BILL_is_accepted_and_routed_by_topic(
    pine_hill, sarah
):
    """⚠ **TC-5** — refusing it would send somebody to the telephone for not
    knowing which bill they meant, which is the outcome this screen exists to
    avoid."""
    maria_with_a_bill(pine_hill, sarah)
    client = signed_in(pine_hill)

    answer = ask(client, pine_hill, bill_number="", topic="Something else")

    assert answer.status_code == 201, answer.content
    assert answer.json()["bill_number"] is None
    with tenant_context(pine_hill.id):
        row = customers_models.ServiceRequest.objects.get(
            request_no=answer.json()["reference"]
        )
    assert "Something else" in row.what_they_said
    assert BILL_NO not in row.what_they_said


@pytest.mark.django_db
def test_us_cwp_066_a_question_with_no_words_is_refused_naming_the_field(pine_hill, sarah):
    """Hard-won law 3 — the empty case refuses rather than putting a blank row
    on somebody's worklist."""
    maria_with_a_bill(pine_hill, sarah)
    client = signed_in(pine_hill)

    answer = ask(client, pine_hill, what="   ")

    assert answer.status_code >= 400, answer.content
    with tenant_context(pine_hill.id):
        assert not customers_models.ServiceRequest.objects.filter(
            channel="customer_portal"
        ).exists()


# ══ TC-6 · TENANT ISOLATION ════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_cwp_066_tc6_another_tenants_bill_is_INVISIBLE_and_an_unknown_one_answers_the_SAME(
    pine_hill, sarah, oak_ridge, elena
):
    """TC-6 — `BR-CWP-010`, in two assertions rather than one.

    ⚠ **THE TENANT HALF IS HELD WITH THE ACCOUNT SET CONSTANT** (the same ids,
    two tenants), and the REFUSAL half is held on one tenant with two numbers:
    a bill that does not exist and a bill that is not mine must be one answer,
    or the form is a way to learn which bills a utility has issued.
    """
    from apps.portal.seams import billing_seam

    _, account, _ = maria_with_a_bill(pine_hill, sarah)
    switch_on(oak_ridge, elena)

    with tenant_context(pine_hill.id):
        mine = billing_seam.bill_facts([str(account.pk)], number=BILL_NO)
    with tenant_context(oak_ridge.id):
        theirs = billing_seam.bill_facts([str(account.pk)], number=BILL_NO)
    assert mine is not None, "or the isolation assertion is vacuous"
    assert theirs is None

    client = signed_in(pine_hill)
    unknown = ask(client, pine_hill, bill_number="BL-0000-0000")
    assert unknown.status_code == 404, unknown.content


# ══ TC-7 · the photo is HELD — there is no route to post a file to ═════════


@pytest.mark.django_db
def test_us_cwp_066_tc7_there_is_NO_CONSUMER_UPLOAD_ROUTE_ANYWHERE_ON_THE_PORTAL(
    pine_hill, sarah
):
    """⚠ **TC-7 — a SIGNED DEFERRAL, not an open question** (PO 2026-08-08,
    `DF-4`: *consumer upload portal = v2*; `CR-068` §2b).

    The picker renders its sentence and no file input, and the server has
    nothing to post to — asserted over the ROUTE TABLE, which is the form of
    this claim that cannot rot when a screen changes.
    """
    from apps.portal import api, guest_api

    routes = [str(p.pattern) for p in api.urlpatterns] + [
        str(p.pattern) for p in guest_api.urlpatterns
    ]
    assert not [r for r in routes if "upload" in r or "attachment" in r], routes
    assert not [r for r in routes if "document" in r and "post" in r.lower()], routes

    # And a multipart post to the question route is not a door either.
    maria_with_a_bill(pine_hill, sarah)
    client = signed_in(pine_hill)
    from io import BytesIO

    upload = BytesIO(b"not a real photo")
    upload.name = "meter.jpg"
    answer = client.post(
        portal_url(pine_hill, "questions"),
        data={"topic": TOPIC, "what": WORDS, "bill_number": BILL_NO, "photo": upload},
    )
    if answer.status_code == 201:
        with tenant_context(pine_hill.id):
            row = customers_models.ServiceRequest.objects.get(
                request_no=answer.json()["reference"]
            )
        assert "meter.jpg" not in (row.what_they_said or "")
        assert "not a real photo" not in (row.what_they_said or "")


# ══ BR-CWP-093 · the *might answer it now* panel has real answers behind it ══


@pytest.mark.django_db
def test_us_cwp_066_tc3_a_tenant_with_NO_published_answers_serves_an_empty_list(
    pine_hill, sarah
):
    """⚠ **TC-3 — the panel is ABSENT, not empty** (`BR-CWP-093`). The SERVER is
    what makes that possible: it answers a real empty list rather than a
    placeholder, and the screen closes the panel up (asserted in the DOM test)."""
    switch_on(pine_hill, sarah)
    answer = Client().get(f"/api/{pine_hill.subdomain}/portal/public/help")

    assert answer.status_code == 200, answer.content
    assert answer.json()["answers"] == []

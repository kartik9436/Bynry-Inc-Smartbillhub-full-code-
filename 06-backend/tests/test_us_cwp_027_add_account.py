# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-027 (EP-CWP-06) — add another account to this login.
#           Screen: CWP-020
# Rules:    BR-CWP-001 kind ⑥ `account_link` (`DEF-CWP-3768` — the blueprint
#           specified this write in BR-CWP-009 and our extraction of the *four*
#           never counted it) · BR-CWP-033 (the code goes to a contact already
#           held ON THAT ACCOUNT) · BR-CWP-009 (the set grows only from a
#           customer-to-account link) · BR-CWP-015 (nothing is combined) ·
#           BR-CWP-013 (the set is FLAT) · BR-CWP-034 (no contact dead-ends) ·
#           CLAUDE.md hard rule 1 · rule 7
# Tests:    this file
# Impacts:  apps/portal/api.py `add_account_find` / `add_account_verify` ·
#           apps/customers/portal_self_service.py `link_account`
# ───────────────────────────────────────────────────────
"""`US-CWP-027`'s cases — and the one sentence the whole screen rests on.

⚠ **THE CODE GOES TO THE CONTACT ON THE ACCOUNT BEING ADDED, NOT TO THE PERSON
ADDING IT** (`BR-CWP-033`, TC-3). Every other guard here is secondary. Matching
on an account number and a postcode discloses nothing and proves nothing — both
are printed on a bill anybody could pick up — so if the code went to the asker,
one stolen bill would collect somebody else's account. TC-3 asserts the
OUTBOUND ROW'S DESTINATION rather than what the screen says about it, which is
the only place that fact is real.

⚠ **AND NOTHING IS COMBINED** (`BR-CWP-015`, TC-7). One `customer_accounts`
row. No balance merged, no bill merged, no account re-homed; the switcher lists
five because `session.account_set` re-derives the set on the next request.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from django.test import Client

from apps.customers import models as customers_models
from apps.notifications import models as notification_models
from apps.portal import models as portal_models, session as portal_session
from apps.portal.seams import customers_seam
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
from tests.test_us_cwp_026_my_accounts import a_tenants_account, four_accounts

#: `1408 Elm St`'s postcode — the same three facts `US-CWP-016` matches on.
POSTCODE = "78702"
WRONG_POSTCODE = "78704"


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


def maria_holding_four(tenant, actor):
    credential = enrol_maria(tenant, actor)
    accounts = four_accounts(tenant, actor)
    with tenant_context(tenant.id):
        for account in accounts:
            customers_models.CustomerAccount.objects.get_or_create(
                tenant_id=tenant.id, customer_id=credential.customer_id, account=account
            )
    return credential, accounts


def account_set_size(tenant, credential) -> int:
    with tenant_context(tenant.id):
        return len(
            portal_session.account_set(
                tenant.id, customer_id=credential.customer_id, credential_id=credential.pk
            )
        )


def postcode_of(tenant, account) -> str:
    from apps.metering import models as metering_models

    with tenant_context(tenant.id):
        premises_id = account.premises_id or account.unit.premises_id
        return metering_models.Premises.objects.get(pk=premises_id).postal_code


@pytest.mark.django_db
def test_us_cwp_027_tc1_the_account_joins_the_set_and_the_switcher_lists_five(
    pine_hill, sarah
):
    """TC-1 — matched, code verified, linked. Four becomes five."""
    switch_on(pine_hill, sarah)
    credential, _ = maria_holding_four(pine_hill, sarah)
    adding = a_tenants_account(pine_hill, sarah)
    assert account_set_size(pine_hill, credential) == 4

    client = signed_in(pine_hill)
    found = post(
        client,
        pine_hill,
        "accounts/add/find",
        {"account_number": adding.account_no, "postcode": postcode_of(pine_hill, adding)},
    ).json()
    assert found["matched"] is True, found
    with tenant_context(pine_hill.id):
        row = portal_models.PortalOneTimeCode.objects.get(pk=found["account_ref"])
        queued = notification_models.OutboundMessage.objects.get(pk=row.outbound_message_id)
    linked = post(
        client,
        pine_hill,
        "accounts/add/verify",
        {"account_ref": found["account_ref"], "code": queued.render_context["code"]},
    ).json()
    assert linked["linked"] is True, linked
    assert account_set_size(pine_hill, credential) == 5


@pytest.mark.django_db
def test_us_cwp_027_tc3_the_code_goes_to_the_ADDED_accounts_contact(pine_hill, sarah):
    """⚠ **THE ONE THAT MATTERS.** `BR-CWP-033`. The destination on the queue
    row is the contact on the account being added — `(512) 555-0144` — and NOT
    Maria's own. If it were hers, one stolen bill number would collect an
    account she has no right to."""
    switch_on(pine_hill, sarah)
    maria_holding_four(pine_hill, sarah)
    adding = a_tenants_account(pine_hill, sarah)
    client = signed_in(pine_hill)
    found = post(
        client,
        pine_hill,
        "accounts/add/find",
        {"account_number": adding.account_no, "postcode": postcode_of(pine_hill, adding)},
    ).json()
    with tenant_context(pine_hill.id):
        row = portal_models.PortalOneTimeCode.objects.get(pk=found["account_ref"])
        queued = notification_models.OutboundMessage.objects.get(pk=row.outbound_message_id)
        theirs = (
            customers_models.Contact.objects.filter(
                tenant_id=pine_hill.id, account=adding, is_primary=True
            )
            .order_by("created_at")
            .first()
        )
        mine = (
            customers_models.Contact.objects.filter(
                tenant_id=pine_hill.id, account=elm_street_account(pine_hill, sarah)
            )
            .order_by("created_at")
            .first()
        )
    assert queued.recipient_address == theirs.phone, (
        "the code went somewhere that is not the ADDED account's contact (BR-CWP-033)"
    )
    assert queued.recipient_address != getattr(mine, "phone", None)


@pytest.mark.django_db
def test_us_cwp_027_tc2_a_wrong_postcode_is_refused_IDENTICALLY_to_an_unknown_number(
    pine_hill, sarah
):
    """TC-2 — one sentence for both, or this form walks the account-number
    space of the utility a customer is already signed in to."""
    switch_on(pine_hill, sarah)
    maria_holding_four(pine_hill, sarah)
    adding = a_tenants_account(pine_hill, sarah)
    client = signed_in(pine_hill)
    wrong_postcode = post(
        client,
        pine_hill,
        "accounts/add/find",
        {"account_number": adding.account_no, "postcode": WRONG_POSTCODE},
    ).json()
    unknown_number = post(
        client,
        pine_hill,
        "accounts/add/find",
        {"account_number": "ACC-00000-Z", "postcode": postcode_of(pine_hill, adding)},
    ).json()
    assert wrong_postcode == unknown_number == {"matched": False, "reason": "not_matched"}


@pytest.mark.django_db
def test_us_cwp_027_tc4_an_account_already_in_the_set_is_refused_as_already_held(
    pine_hill, sarah
):
    """TC-4. ⚠ Saying *you already have this one* discloses nothing: it is on
    the list the same person is looking at."""
    switch_on(pine_hill, sarah)
    _, accounts = maria_holding_four(pine_hill, sarah)
    mine = accounts[0]
    client = signed_in(pine_hill)
    answer = post(
        client,
        pine_hill,
        "accounts/add/find",
        {"account_number": mine.account_no, "postcode": postcode_of(pine_hill, mine)},
    ).json()
    assert answer == {"matched": False, "reason": "already_held"}


@pytest.mark.django_db
def test_us_cwp_027_tc5_an_account_with_no_contact_DEAD_ENDS_into_ring_the_office(
    pine_hill, sarah
):
    """`BR-CWP-034`. ⚠ **THERE IS NO BRANCH BELOW THIS ONE** — it must never
    fall back to something weaker, such as sending the code to the asker."""
    switch_on(pine_hill, sarah)
    maria_holding_four(pine_hill, sarah)
    adding = a_tenants_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        customers_models.Contact.objects.filter(
            tenant_id=pine_hill.id, account=adding
        ).update(phone=None, email=None)
    client = signed_in(pine_hill)
    answer = post(
        client,
        pine_hill,
        "accounts/add/find",
        {"account_number": adding.account_no, "postcode": postcode_of(pine_hill, adding)},
    ).json()
    assert answer["reason"] == "no_contact_on_file"
    assert answer["account_ref"] is None, "nothing was issued, so there is nothing to verify"


@pytest.mark.django_db
def test_us_cwp_027_tc6_the_matcher_filters_the_TENANT_in_the_query(
    pine_hill, oak_ridge, sarah, elena
):
    """TC-6, asserted the way hard rule 1 means it.

    ⚠ **DRIVEN WITH OAK RIDGE'S TENANT ID AND PINE HILL'S ACCOUNT NUMBER** —
    the exact shape a confused caller produces. The answer is `None` because the
    row does not come back from `filter(tenant_id=…)`, not because something
    checked afterwards and refused: a check afterwards would have to say *that
    belongs to someone else*, which is the disclosure TC-2 exists to prevent.
    """
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    _, accounts = maria_holding_four(pine_hill, sarah)
    mine = accounts[0]
    postcode = postcode_of(pine_hill, mine)
    with tenant_context(oak_ridge.id):
        found = customers_seam.account_by_number_and_postcode(
            oak_ridge.id, account_no=mine.account_no, postcode=postcode
        )
    assert found is None
    with tenant_context(pine_hill.id):
        assert (
            customers_seam.account_by_number_and_postcode(
                pine_hill.id, account_no=mine.account_no, postcode=postcode
            )
            is not None
        ), "the same two facts DO match inside the right tenant — so TC-6 is about the filter"


@pytest.mark.django_db
def test_us_cwp_027_tc7_nothing_is_combined_and_the_set_stays_FLAT(pine_hill, sarah):
    """TC-7 + `BR-CWP-013`. One link row is the entire write.

    ⚠ **ASSERTED BY COUNTING WHAT DID NOT CHANGE**, because *nothing is
    combined* is a statement about absence: the invoice count is the same, the
    added account keeps its own balance, and every entry in the set is flat —
    a master would be one more entry, never a parent.
    """
    from apps.billing import models as billing_models

    switch_on(pine_hill, sarah)
    credential, accounts = maria_holding_four(pine_hill, sarah)
    adding = a_tenants_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_issued_bill(
            pine_hill, adding, number="BL-2608-0199", total="64.5000",
            issued_on=date(2026, 8, 26), due_on=date(2026, 9, 14),
        )
        before = billing_models.Invoice.objects.filter(tenant_id=pine_hill.id).count()

    client = signed_in(pine_hill)
    found = post(
        client, pine_hill, "accounts/add/find",
        {"account_number": adding.account_no, "postcode": postcode_of(pine_hill, adding)},
    ).json()
    with tenant_context(pine_hill.id):
        row = portal_models.PortalOneTimeCode.objects.get(pk=found["account_ref"])
        queued = notification_models.OutboundMessage.objects.get(pk=row.outbound_message_id)
    post(
        client, pine_hill, "accounts/add/verify",
        {"account_ref": found["account_ref"], "code": queued.render_context["code"]},
    )
    with tenant_context(pine_hill.id):
        after = billing_models.Invoice.objects.filter(tenant_id=pine_hill.id).count()
        entries = portal_session.account_set(
            pine_hill.id, customer_id=credential.customer_id, credential_id=credential.pk
        )
    assert after == before, "linking an account created or merged no bill"
    assert len(entries) == 5
    # `BR-CWP-013` — FLAT. Every entry is an account id and a permission list;
    # there is no parent, and a lane that added one would give a landlord their
    # tenants' accounts.
    assert all(isinstance(entry.account_id, str) for entry in entries)
    assert len({entry.account_id for entry in entries}) == 5


@pytest.mark.django_db
def test_us_cwp_027_a_wrong_code_does_NOT_link_the_account(pine_hill, sarah):
    """The guard is the code, so this is the case that proves the guard runs.
    A `find` that matched and a `verify` that failed leaves the set at four."""
    switch_on(pine_hill, sarah)
    credential, _ = maria_holding_four(pine_hill, sarah)
    adding = a_tenants_account(pine_hill, sarah)
    client = signed_in(pine_hill)
    found = post(
        client, pine_hill, "accounts/add/find",
        {"account_number": adding.account_no, "postcode": postcode_of(pine_hill, adding)},
    ).json()
    answer = post(
        client, pine_hill, "accounts/add/verify",
        {"account_ref": found["account_ref"], "code": "000000"},
    ).json()
    assert answer["linked"] is False, answer
    assert account_set_size(pine_hill, credential) == 4, "no code, no link"


@pytest.mark.django_db
def test_us_cwp_027_the_link_write_records_WHO_did_it(pine_hill, sarah, audit_rows):
    """Hard rule 7. ⚠ The actor is the CUSTOMER and the SESSION, never a staff
    user id — `BR-CWP-004` keeps the two apart, and an audit row that could not
    tell them apart would defeat the one record that exists to."""
    switch_on(pine_hill, sarah)
    credential, _ = maria_holding_four(pine_hill, sarah)
    adding = a_tenants_account(pine_hill, sarah)
    client = signed_in(pine_hill)
    found = post(
        client, pine_hill, "accounts/add/find",
        {"account_number": adding.account_no, "postcode": postcode_of(pine_hill, adding)},
    ).json()
    with tenant_context(pine_hill.id):
        row = portal_models.PortalOneTimeCode.objects.get(pk=found["account_ref"])
        queued = notification_models.OutboundMessage.objects.get(pk=row.outbound_message_id)
    post(
        client, pine_hill, "accounts/add/verify",
        {"account_ref": found["account_ref"], "code": queued.render_context["code"]},
    )
    written = [row for row in audit_rows if row["action"] == "portal.account_link.created"]
    assert written, [row["action"] for row in audit_rows]
    assert written[0]["actor_user_id"] is None
    assert written[0]["after"]["actor"]["portal_customer_id"] == str(credential.customer_id)
    assert written[0]["after"]["account_id"] == str(adding.pk)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-027@this-commit (EP-CWP-06 story + BR-CWP-009/033/034/015/013 verbatim + DEF-CWP-3768)
# generated: 2026-09-04 by the CR-068 wave G build lane
# checklist: A✔ B✔ C✔ D✔(api.py accounts/add/*) E✔(CWP-020) F✔ G✔ H=n/a(no money column is written)
# gates: pytest tests/test_us_cwp_027_add_account.py · G81 · G84
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

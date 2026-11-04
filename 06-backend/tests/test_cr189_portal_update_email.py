# ── Trace ──────────────────────────────────────────────
# Change:   CR-189-BRC10 — the locked-out customer's "update your registered
#           email" path (CWP-019U, `/{tenant}/portal/update-email`)
# Rules:    decision log 2026-10-22 (the CR-189 entries) · BR-CWP-023 ·
#           BR-CWP-030/031/032/033/034/035 · hard rules 1 and 7
# Tests:    this file (SQLite) · test_cr189_portal_update_email_pg.py (PG)
# Impacts:  apps/portal/email_update.py · email_update_api.py
# ───────────────────────────────────────────────────────
"""Each case is the breach it would catch, asserted on the QUEUE and the
database, never only on the screen's words."""

from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.customers import models as customers_models
from apps.notifications import models as notification_models
from apps.portal import email_update
from apps.portal import models as portal_models
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import MARIA_EMAIL, elm_street_account, enrol_maria, switch_on

FACTS = {"postcode": "78702", "last_name": "Alvarez"}
NEW_EMAIL = "maria.new@example.test"


def post(tenant, path: str, body: dict):
    return Client().post(
        f"/api/{tenant.subdomain}/portal/update-email/{path}",
        data=json.dumps(body),
        content_type="application/json",
    )


@pytest.fixture
def sent_now(monkeypatch):
    """Spy on the instant sender. Absent on this base until STAFF-INVITE lands,
    so it is planted by name — exactly how the portal resolves it."""
    from apps.notifications import services

    calls: list[list] = []
    monkeypatch.setattr(
        services, "send_now", lambda ids, actor=None: calls.append(list(ids)), raising=False
    )
    return calls


def live(tenant, actor):
    switch_on(tenant, actor)
    return elm_street_account(tenant, actor)


def queued(tenant, row_id):
    with tenant_context(tenant.id):
        row = portal_models.PortalOneTimeCode.objects.get(pk=row_id)
        return notification_models.OutboundMessage.objects.get(pk=row.outbound_message_id)


def prove(tenant, account):
    """Steps 1–3: the facts, the first option, its code off the queue."""
    found = post(tenant, "find", {"account_number": account.account_no, **FACTS}).json()
    assert found["matched"] is True and found["ref"], found
    option = found["options"][0]
    sent = post(tenant, "send-code", {"ref": found["ref"], "option": option["key"]}).json()
    assert sent["sent"] is True, sent
    code = queued(tenant, sent["ref"]).render_context["code"]
    verdict = post(tenant, "verify-code", {"ref": sent["ref"], "code": code}).json()
    assert verdict["result"] == "ok", verdict
    return found, sent


def start(tenant, proven_ref, email=NEW_EMAIL):
    body = post(tenant, "new-email", {"ref": proven_ref, "email": email}).json()
    assert body["ok"] is True, body
    return body


# ══ the whole path ══════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_happy_path_changes_login_and_contact_notifies_old_and_sends_reset(
    pine_hill, sarah, sent_now, audit_rows, settings
):
    # The reset step is PORTAL-RESET's `credentials.send_reset`, which mints
    # nothing without a public address (law 3) — so the test names one.
    settings.PUBLIC_APP_ORIGIN = "https://app.example.test"
    credential = enrol_maria(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    switch_on(pine_hill, sarah)
    found, sent = prove(pine_hill, account)
    # The masked option and nothing else about the account (BR-CWP-032).
    assert set(found) <= {"matched", "ref", "options", "office"}
    assert all("555" not in option["masked"] for option in found["options"])

    started = start(pine_hill, sent["ref"])
    message = queued(pine_hill, started["ref"])
    assert message.recipient_address == NEW_EMAIL
    assert message.template_code == email_update.TEMPLATE_CONFIRM_CODE
    code = message.render_context["code"]

    # Before confirming, NOTHING has moved (a new email never takes effect first).
    with tenant_context(pine_hill.id):
        credential.refresh_from_db()
    assert credential.email == MARIA_EMAIL

    done = post(
        pine_hill, "confirm", {"ref": started["ref"], "code": code, "email": NEW_EMAIL}
    ).json()
    assert done == {"ok": True, "next": "check_email", "sent_to": "m•••@example.test"}, done

    with tenant_context(pine_hill.id):
        credential.refresh_from_db()
        assert credential.email == NEW_EMAIL
        contact = (
            customers_models.Contact.objects.filter(account_id=account.pk, is_primary=True)
            .order_by("created_at")
            .first()
        )
        assert contact.email == NEW_EMAIL
        notice = notification_models.OutboundMessage.objects.get(
            template_code=email_update.TEMPLATE_CHANGED_NOTICE
        )
        assert notice.recipient_address == MARIA_EMAIL
        reset = portal_models.PortalOneTimeCode.objects.filter(
            purpose=portal_models.PURPOSE_RESET, portal_credential_id=credential.pk
        ).first()
        assert reset is not None and reset.outbound_message_id is not None
        reset_message = notification_models.OutboundMessage.objects.get(
            pk=reset.outbound_message_id
        )
        assert reset_message.recipient_address == NEW_EMAIL
        assert reset_message.template_code == "portal_password_reset"
        # The link's secret is in the FRAGMENT (decision log 2026-10-22).
        reset_link = reset_message.render_context["reset_link"]
        assert "?" not in reset_link and "#ref=" in reset_link
    actions = {row["action"] for row in audit_rows}
    assert {"portal_credential.email_changed", "portal.contact_detail.updated"} <= actions
    # Every account-access message went to the instant sender.
    flat = {str(one) for call in sent_now for one in call}
    assert str(message.pk) in flat and str(notice.pk) in flat
    assert str(reset_message.pk) in flat


@pytest.mark.django_db
def test_no_login_yet_updates_the_contact_and_points_to_sign_up(pine_hill, sarah, sent_now):
    account = live(pine_hill, sarah)
    _found, sent = prove(pine_hill, account)
    started = start(pine_hill, sent["ref"])
    code = queued(pine_hill, started["ref"]).render_context["code"]
    done = post(
        pine_hill, "confirm", {"ref": started["ref"], "code": code, "email": NEW_EMAIL}
    ).json()
    assert done["ok"] is True and done["next"] == "enrol", done
    with tenant_context(pine_hill.id):
        assert portal_models.PortalCredential.objects.count() == 0
        assert not portal_models.PortalOneTimeCode.objects.filter(
            purpose=portal_models.PURPOSE_RESET
        ).exists()


# ══ refusals ════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_wrong_surname_and_unknown_number_answer_identically(pine_hill, sarah):
    account = live(pine_hill, sarah)
    wrong = post(
        pine_hill,
        "find",
        {"account_number": account.account_no, "postcode": "78702", "last_name": "Nobody"},
    )
    unknown = post(pine_hill, "find", {"account_number": "ACC-00000-Z", **FACTS})
    assert wrong.content == unknown.content == b'{"matched":false,"reason":"not_matched"}'


@pytest.mark.django_db
def test_five_wrong_tries_lock_for_fifteen_minutes_even_with_correct_facts(pine_hill, sarah):
    account = live(pine_hill, sarah)
    reasons = [
        post(pine_hill, "find", {"account_number": "ACC-00000-Z", **FACTS}).json()["reason"]
        for _ in range(5)
    ]
    assert reasons == ["not_matched"] * 4 + ["locked"], reasons
    correct = post(pine_hill, "find", {"account_number": account.account_no, **FACTS}).json()
    assert correct == {"matched": False, "reason": "locked"}


@pytest.mark.django_db
def test_wrong_and_reused_codes_are_refused(pine_hill, sarah):
    account = live(pine_hill, sarah)
    found = post(pine_hill, "find", {"account_number": account.account_no, **FACTS}).json()
    sent = post(
        pine_hill, "send-code", {"ref": found["ref"], "option": found["options"][0]["key"]}
    ).json()
    assert post(pine_hill, "verify-code", {"ref": sent["ref"], "code": "000000"}).json() == {
        "result": "wrong"
    }
    # Not proven ⇒ the new-email step refuses.
    assert (
        post(pine_hill, "new-email", {"ref": sent["ref"], "email": NEW_EMAIL}).json()["reason"]
        == "start_again"
    )
    # A key that is not one of the options sends nothing.
    assert (
        post(pine_hill, "send-code", {"ref": found["ref"], "option": "nope"}).json()["sent"]
        is False
    )


@pytest.mark.django_db
def test_expired_code_is_its_own_answer(pine_hill, sarah):
    from datetime import timedelta

    from django.utils import timezone

    account = live(pine_hill, sarah)
    found = post(pine_hill, "find", {"account_number": account.account_no, **FACTS}).json()
    sent = post(
        pine_hill, "send-code", {"ref": found["ref"], "option": found["options"][0]["key"]}
    ).json()
    code = queued(pine_hill, sent["ref"]).render_context["code"]
    with tenant_context(pine_hill.id):
        portal_models.PortalOneTimeCode.objects.filter(pk=sent["ref"]).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
    assert post(pine_hill, "verify-code", {"ref": sent["ref"], "code": code}).json() == {
        "result": "expired"
    }


@pytest.mark.django_db
def test_confirmation_code_is_bound_to_the_address_it_was_sent_to(pine_hill, sarah, sent_now):
    enrol_maria(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    switch_on(pine_hill, sarah)
    _found, sent = prove(pine_hill, account)
    started = start(pine_hill, sent["ref"])
    code = queued(pine_hill, started["ref"]).render_context["code"]
    swapped = post(
        pine_hill, "confirm", {"ref": started["ref"], "code": code, "email": "thief@example.test"}
    ).json()
    assert swapped == {"ok": False, "reason": "wrong"}
    with tenant_context(pine_hill.id):
        assert portal_models.PortalCredential.objects.get().email == MARIA_EMAIL


@pytest.mark.django_db
def test_an_address_that_is_another_login_gets_the_same_answer_and_no_code(
    pine_hill, sarah, sent_now, audit_rows
):
    account = live(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        # Another customer of the same utility, holding a login at the address.
        stranger = customers_models.Customer.objects.create(
            tenant_id=pine_hill.id, display_name="Dana Okafor"
        )
        portal_models.PortalCredential.objects.create(
            tenant_id=pine_hill.id,
            customer_id=stranger.pk,
            email="taken@example.test",
            password_hash="!",
        )
    _found, sent = prove(pine_hill, account)
    taken = post(pine_hill, "new-email", {"ref": sent["ref"], "email": "taken@example.test"}).json()
    free = post(pine_hill, "new-email", {"ref": sent["ref"], "email": "free@example.test"}).json()
    assert set(taken) == set(free) and taken["ok"] is free["ok"] is True
    assert taken["expires_in_minutes"] == free["expires_in_minutes"]
    with tenant_context(pine_hill.id):
        assert not notification_models.OutboundMessage.objects.filter(
            recipient_address="taken@example.test"
        ).exists()
    refused = [
        row for row in audit_rows if row["action"] == "portal_credential.email_update_refused"
    ]
    assert len(refused) == 1


@pytest.mark.django_db
def test_no_contact_on_file_dead_ends_with_the_office_number(pine_hill, sarah):
    account = live(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        customers_models.Contact.objects.filter(account_id=account.pk).update(
            phone=None, email=None
        )
        type(pine_hill).objects.filter(pk=pine_hill.pk).update(support_phone="(512) 555-0148")
    body = post(pine_hill, "find", {"account_number": account.account_no, **FACTS}).json()
    assert body["matched"] is True and body["reason"] == "no_contact_on_file"
    assert body["ref"] is None and "options" not in body
    assert body["office"]["phone"] == "(512) 555-0148"


@pytest.mark.django_db
def test_a_ref_from_one_utility_is_nothing_at_another(pine_hill, sarah, oak_ridge, elena):
    account = live(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    found = post(pine_hill, "find", {"account_number": account.account_no, **FACTS}).json()
    key = found["options"][0]["key"]
    across = post(oak_ridge, "send-code", {"ref": found["ref"], "option": key}).json()
    assert across == {"sent": False, "reason": "start_again"}


@pytest.mark.django_db
def test_seeded_wording_is_written_in_every_registry_language_and_passes_the_palette():
    from apps.notifications import account_access_wording, rendering
    from apps.tenancy.services import SEED_LANGUAGES

    for code in (
        email_update.TEMPLATE_ON_FILE_CODE,
        email_update.TEMPLATE_CONFIRM_CODE,
        email_update.TEMPLATE_CHANGED_NOTICE,
    ):
        for language in SEED_LANGUAGES:
            words = account_access_wording.wording_for(code, language)
            assert words is not None, f"{code} has no {language} wording"
            subject, body = words
            rendering.validate_body(code, body, subject=subject)


@pytest.mark.django_db
def test_every_row_the_flow_queues_can_be_kept_and_dispatched(pine_hill, sarah, sent_now):
    """Decision log 2026-10-22: account-access emails are KEPT like every other
    document, the code redacted in the kept copy. A class with no document kind
    is refused `document_kind_not_ruled` and waits in the queue for ever, so
    each row this flow writes must have one, and each code class must name its
    code as a credential token."""
    from apps.notifications import catalogs, frozen_documents

    enrol_maria(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    switch_on(pine_hill, sarah)
    _found, sent = prove(pine_hill, account)
    started = start(pine_hill, sent["ref"])
    code = queued(pine_hill, started["ref"]).render_context["code"]
    post(pine_hill, "confirm", {"ref": started["ref"], "code": code, "email": NEW_EMAIL})
    with tenant_context(pine_hill.id):
        rows = list(
            notification_models.OutboundMessage.objects.filter(source_type="portal").exclude(
                template_code="portal_password_reset"
            )
        )
    codes = {row.template_code for row in rows}
    assert {
        email_update.TEMPLATE_ON_FILE_CODE,
        email_update.TEMPLATE_CONFIRM_CODE,
        email_update.TEMPLATE_CHANGED_NOTICE,
    } <= codes, codes
    for row in rows:
        assert frozen_documents.document_kind(row) is not None, (
            f"{row.template_code} would be refused {frozen_documents.FREEZE_KIND_UNRULED}"
        )
    for code_class in (email_update.TEMPLATE_ON_FILE_CODE, email_update.TEMPLATE_CONFIRM_CODE):
        assert "code" in catalogs.catalog_for(code_class).credential_tokens

# ── Trace ──────────────────────────────────────────────
# Change:   CR-189-BRC10 — who moves the portal sign-in email (PO 2026-10-22):
#           the clerk's tick box (closes OQ-CUS-12350, DEF-CWP-10400) and the
#           signed-in change confirmed by a code to the new address
#           (DEF-CWP-10401).
# Rules:    decision log 2026-10-22 "Who moves the portal sign-in email…" and
#           "…built: the judgments the two rulings left to us" · BR-CWP-010 ·
#           BR-CWP-026 · BR-CWP-038 · B2 §2 · hard rules 1 and 7
# Tests:    this file (SQLite) · test_cr189_signin_email_pg.py (PostgreSQL)
# Impacts:  apps/customers/customer_edit.py · services.update_account_contact ·
#           portal_seam.py · apps/portal/email_update.py · email_update_api.py ·
#           api.save_my_details
# ───────────────────────────────────────────────────────
"""Each case is the defect it would catch, asserted on the login row, the
contact rows and the queue — never only on a response's words."""

from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.customers import customer_edit
from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.notifications import models as notification_models
from apps.portal import credentials, email_update
from apps.portal import models as portal_models
from core import errors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    elm_street_account,
    enrol_maria,
    switch_on,
)

NEW_EMAIL = "maria.new@example.test"
OTHER_EMAIL = "someone.else@example.test"


@pytest.fixture
def sent_now(monkeypatch):
    from apps.notifications import services

    calls: list[list] = []
    monkeypatch.setattr(
        services, "send_now", lambda ids, actor=None: calls.append(list(ids)), raising=False
    )
    return calls


def _maria(tenant, actor):
    switch_on(tenant, actor)
    account = elm_street_account(tenant, actor)
    credential = enrol_maria(tenant, actor)
    return credential, account


def _messages(tenant, template_code):
    with tenant_context(tenant.id):
        return list(
            notification_models.OutboundMessage.objects.filter(template_code=template_code)
        )


def _contact_emails(tenant, customer_id):
    with tenant_context(tenant.id):
        ids = customers_models.CustomerAccount.live(
            tenant_id=tenant.id, customer_id=customer_id
        ).values_list("account_id", flat=True)
        return set(
            customers_models.Contact.objects.filter(
                account_id__in=list(ids), is_primary=True, deleted_at__isnull=True
            ).values_list("email", flat=True)
        )


def _second_login(tenant, account, email=OTHER_EMAIL):
    """Another customer of the same utility with a login, holding `account` too."""
    with tenant_context(tenant.id):
        other = customers_models.Customer.objects.create(
            tenant_id=tenant.id, display_name="Whitfield, Dana", kind="person"
        )
        customers_models.CustomerAccount.objects.create(
            tenant_id=tenant.id, customer=other, account=account
        )
        return portal_models.PortalCredential.objects.create(
            tenant_id=tenant.id, customer=other, email=email, password_hash="x"
        )


# ══ 1 · the clerk's tick box ═══════════════════════════════════════════════


@pytest.mark.django_db
def test_ticked_moves_the_login_notifies_the_old_address_and_sends_a_reset(
    pine_hill, sarah, sent_now, audit_rows, settings
):
    """DEF-CWP-10400: the *Call the office* ending. The clerk moves the email
    with the box ticked; forgot-password at the NEW address now finds a login."""
    settings.PUBLIC_APP_ORIGIN = "https://app.example.test"
    credential, _account = _maria(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        result = customer_edit.update_customer(
            sarah,
            str(credential.customer_id),
            {"email": NEW_EMAIL, "portal_sign_in": True},
        )
        credential.refresh_from_db()
    assert result["portal_sign_in_moved"] is True
    assert credential.email == NEW_EMAIL
    assert _contact_emails(pine_hill, credential.customer_id) == {NEW_EMAIL}

    [notice] = _messages(pine_hill, email_update.TEMPLATE_CHANGED_NOTICE)
    assert notice.recipient_address == MARIA_EMAIL
    [reset] = _messages(pine_hill, "portal_password_reset")
    assert reset.recipient_address == NEW_EMAIL
    assert "#ref=" in reset.render_context["reset_link"]
    flat = {str(one) for call in sent_now for one in call}
    assert {str(notice.pk), str(reset.pk)} <= flat

    moved = [row for row in audit_rows if row["action"] == "portal_credential.email_changed"]
    assert len(moved) == 1 and str(moved[0]["actor_user_id"]) == str(sarah.id), moved

    # …and the customer's own Forgot-your-password at the new address now
    # reaches a login (it found none before this fix).
    answer = Client().post(
        f"/api/{pine_hill.subdomain}/portal/auth/forgot-password",
        data=json.dumps({"email": NEW_EMAIL}),
        content_type="application/json",
    )
    assert answer.status_code == 200
    assert len(_messages(pine_hill, "portal_password_reset")) == 2


@pytest.mark.django_db
def test_unticked_keeps_the_two_separate_exactly_as_before(pine_hill, sarah, sent_now):
    credential, _account = _maria(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        result = customer_edit.update_customer(
            sarah, str(credential.customer_id), {"email": NEW_EMAIL}
        )
        credential.refresh_from_db()
    assert result["portal_sign_in_moved"] is False
    assert credential.email == MARIA_EMAIL
    assert _contact_emails(pine_hill, credential.customer_id) == {NEW_EMAIL}
    assert _messages(pine_hill, email_update.TEMPLATE_CHANGED_NOTICE) == []
    assert _messages(pine_hill, "portal_password_reset") == []


@pytest.mark.django_db
def test_ticked_over_another_customers_login_is_refused_and_nothing_is_saved(
    pine_hill, sarah, sent_now
):
    credential, account = _maria(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        portal_models.PortalCredential.objects.create(
            tenant_id=pine_hill.id,
            customer=customers_models.Customer.objects.create(
                tenant_id=pine_hill.id, display_name="Other, Person", kind="person"
            ),
            email=OTHER_EMAIL,
            password_hash="x",
        )
    before = _contact_emails(pine_hill, credential.customer_id)
    with tenant_context(pine_hill.id):
        with pytest.raises(errors.ValidationError) as caught:
            customer_edit.update_customer(
                sarah, str(credential.customer_id), {"email": OTHER_EMAIL, "portal_sign_in": True}
            )
        credential.refresh_from_db()
    assert caught.value.message_key == "customers.customer.edit.signInTaken"
    assert credential.email == MARIA_EMAIL
    assert _contact_emails(pine_hill, credential.customer_id) == before
    assert _messages(pine_hill, email_update.TEMPLATE_CHANGED_NOTICE) == []


@pytest.mark.django_db
def test_ticked_with_no_login_or_no_email_is_refused_by_name(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        customer_id = (
            customers_models.CustomerAccount.live(tenant_id=pine_hill.id, account_id=account.pk)
            .values_list("customer_id", flat=True)
            .first()
        )
        with pytest.raises(errors.ValidationError) as no_login:
            customer_edit.update_customer(
                sarah, str(customer_id), {"email": NEW_EMAIL, "portal_sign_in": True}
            )
    assert no_login.value.message_key == "customers.customer.edit.signInNoLogin"

    credential = enrol_maria(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        with pytest.raises(errors.ValidationError) as blank:
            customer_edit.update_customer(
                sarah, str(credential.customer_id), {"email": "", "portal_sign_in": True}
            )
    assert blank.value.message_key == "customers.customer.edit.signInNeedsEmail"


@pytest.mark.django_db
def test_the_customer_row_says_whether_there_is_a_login(pine_hill, sarah):
    credential, _account = _maria(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        customers_models.Customer.objects.create(
            tenant_id=pine_hill.id, display_name="Nologin, Nora", kind="person"
        )
        row = customers_selectors.customer_detail(credential.customer_id)
        page = customers_selectors.customer_rows(
            list(customers_models.Customer.objects.filter(tenant_id=pine_hill.id))
        )
    assert row["has_portal_login"] is True
    by_id = {one["id"]: one["has_portal_login"] for one in page}
    assert by_id[str(credential.customer_id)] is True
    assert False in by_id.values(), "a customer without a login reads False"


@pytest.mark.django_db
def test_the_account_pencil_moves_the_one_login_and_refuses_a_joint_account(
    pine_hill, sarah, sent_now, settings
):
    settings.PUBLIC_APP_ORIGIN = "https://app.example.test"
    credential, account = _maria(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        done = customers_services.update_account_contact(
            sarah, str(account.pk), {"email": NEW_EMAIL, "portal_sign_in": True}
        )
        credential.refresh_from_db()
    assert done["portal_sign_in_moved"] is True and credential.email == NEW_EMAIL

    _second_login(pine_hill, account)
    with tenant_context(pine_hill.id):
        with pytest.raises(errors.ValidationError) as joint:
            customers_services.update_account_contact(
                sarah, str(account.pk), {"email": "third@example.test", "portal_sign_in": True}
            )
        credential.refresh_from_db()
        contact = customers_models.Contact.objects.filter(
            account_id=account.pk, is_primary=True
        ).first()
    assert joint.value.message_key == "customers.account.edit.signInJoint"
    assert credential.email == NEW_EMAIL and contact.email == NEW_EMAIL


# ══ 2 · the signed-in change, confirmed by a code ═══════════════════════════


def _signed_in(tenant):
    client = Client()
    answer = client.post(
        f"/api/{tenant.subdomain}/portal/auth/sign-in",
        data=json.dumps({"email": MARIA_EMAIL, "password": MARIA_PASSWORD}),
        content_type="application/json",
    )
    assert answer.status_code == 200, answer.content
    return client


def _post(client, tenant, path, body):
    return client.post(
        f"/api/{tenant.subdomain}/portal/{path}",
        data=json.dumps(body),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_signed_in_save_no_longer_moves_the_email_but_still_saves_the_phone(pine_hill, sarah):
    credential, _account = _maria(pine_hill, sarah)
    client = _signed_in(pine_hill)
    shown = client.get(f"/api/{pine_hill.subdomain}/portal/my-details").json()["email"]
    before = _contact_emails(pine_hill, credential.customer_id)

    refused = _post(client, pine_hill, "my-details/save", {"email": NEW_EMAIL})
    assert refused.status_code in (400, 409, 422), refused.content
    assert b"portal.myDetails.emailNeedsCode" in refused.content
    assert _contact_emails(pine_hill, credential.customer_id) == before

    kept = _post(
        client, pine_hill, "my-details/save", {"email": shown, "phone": "(512) 555-9911"}
    )
    assert kept.status_code == 200, kept.content
    assert _contact_emails(pine_hill, credential.customer_id) == before


@pytest.mark.django_db
def test_signed_in_code_to_the_new_address_then_both_move_and_the_old_is_told(
    pine_hill, sarah, sent_now
):
    credential, _account = _maria(pine_hill, sarah)
    client = _signed_in(pine_hill)

    started = _post(client, pine_hill, "my-details/email/start", {"email": NEW_EMAIL}).json()
    assert started["ok"] is True and started["sent_to"] == "m•••@example.test", started
    [code_message] = _messages(pine_hill, email_update.TEMPLATE_CONFIRM_CODE)
    assert code_message.recipient_address == NEW_EMAIL
    code = code_message.render_context["code"]
    with tenant_context(pine_hill.id):
        credential.refresh_from_db()
    assert credential.email == MARIA_EMAIL, "nothing moves before the code comes back"

    # The code is bound to the address: the right code beside another address fails.
    wrong_address = _post(
        client,
        pine_hill,
        "my-details/email/confirm",
        {"ref": started["ref"], "code": code, "email": "maria.typo@example.test"},
    ).json()
    assert wrong_address == {"ok": False, "reason": "wrong"}

    done = _post(
        client,
        pine_hill,
        "my-details/email/confirm",
        {"ref": started["ref"], "code": code, "email": NEW_EMAIL},
    ).json()
    assert done["ok"] is True, done
    with tenant_context(pine_hill.id):
        credential.refresh_from_db()
    assert credential.email == NEW_EMAIL
    assert _contact_emails(pine_hill, credential.customer_id) == {NEW_EMAIL}
    [notice] = _messages(pine_hill, email_update.TEMPLATE_CHANGED_NOTICE)
    assert notice.recipient_address == MARIA_EMAIL
    assert _messages(pine_hill, "portal_password_reset") == [], "signed in: no reset link"
    flat = {str(one) for call in sent_now for one in call}
    assert {str(code_message.pk), str(notice.pk)} <= flat


@pytest.mark.django_db
def test_signed_in_change_to_another_login_gets_the_same_answer_and_no_code(
    pine_hill, sarah, sent_now
):
    credential, account = _maria(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        portal_models.PortalCredential.objects.create(
            tenant_id=pine_hill.id,
            customer=customers_models.Customer.objects.create(
                tenant_id=pine_hill.id, display_name="Other, Person", kind="person"
            ),
            email=OTHER_EMAIL,
            password_hash="x",
        )
    client = _signed_in(pine_hill)
    taken = _post(client, pine_hill, "my-details/email/start", {"email": OTHER_EMAIL}).json()
    free = _post(client, pine_hill, "my-details/email/start", {"email": NEW_EMAIL}).json()
    assert set(taken) == set(free) and taken["ok"] is True
    assert [m.recipient_address for m in _messages(pine_hill, email_update.TEMPLATE_CONFIRM_CODE)] == [
        NEW_EMAIL
    ]
    unchanged = _post(client, pine_hill, "my-details/email/start", {"email": MARIA_EMAIL}).json()
    assert unchanged == {"ok": False, "reason": "unchanged"}


@pytest.mark.django_db
def test_the_signed_in_routes_refuse_a_guest(pine_hill, sarah):
    _maria(pine_hill, sarah)
    answer = _post(Client(), pine_hill, "my-details/email/start", {"email": NEW_EMAIL})
    assert answer.status_code in (401, 403), answer.content

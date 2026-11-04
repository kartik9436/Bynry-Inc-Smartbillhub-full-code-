# ── Trace ──────────────────────────────────────────────
# Change:   CR-188-BRC10 — PO 2026-10-22, decision logs *"Staff invitation
#           email: a one-time sign-in link, not a password; six answers"*,
#           *"Account-access emails are sent instantly, at the highest
#           priority"*, *"Account-access emails: languages via template
#           variants, and 'don't do any hardcoding'"*
# Rules:    BR-IDN-021 (SUPERSEDED for invitations and resets) · BR-IDN-002 ·
#           BR-IDN-011 · BR-IDN-022/023/025 · BR-NOT-006 · CLAUDE.md rule 1
# ───────────────────────────────────────────────────────
"""Create user / Reset / Resend email a ONE-TIME SIGN-IN LINK, never a password;
the link sets the person's own password once, and only while it is live."""

from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from django.test import Client

from apps.identity import password_links
from apps.identity.models import PasswordLink, SecurityPolicy, TenantMembership, User
from apps.notifications import account_access_wording, catalogs, rendering, seed_templates
from apps.notifications import models as nm
from apps.notifications import staff_access_events, tenancy_seam
from apps.notifications import template_models as tm
from core import tenancy as core_tenancy
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    SC,
    api_post,
    api_sign_in,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

ORIGIN = "https://app-sand.bynry.com"
NEW_PASSWORD = "Willow2026brook"


@pytest.fixture(autouse=True)
def _fresh_throttle():
    """The public link doors allow ten calls a minute per address, and every
    case here comes from the same test address — so each case starts with an
    empty throttle history rather than inheriting its neighbours' calls."""
    from django.core.cache import cache

    cache.clear()


@pytest.fixture()
def mail(idn, settings, monkeypatch):
    """A utility whose email CAN leave: a public address and a connected provider."""
    settings.PUBLIC_APP_ORIGIN = ORIGIN
    monkeypatch.setattr(staff_access_events, "email_reachability", lambda: None)
    return idn


def _rows():
    return list(nm.OutboundMessage.objects.filter(source_type="staff_access").order_by("created_at"))


def _token(row) -> str:
    link = row.render_context["sign_in_link"]
    # The token travels in the FRAGMENT (decision log 2026-10-22, MERGE-ACCESS).
    parts = urlsplit(link)
    assert parts.query == "", "a one-time secret in the query string reaches server logs"
    return parse_qs(parts.fragment)["token"][0]


def _add(client, email="tom@silvercreek.example", name="Tom Nguyen"):
    return api_post(client, "/users", {"full_name": name, "email": email, "role": "billing_clerk"})


def _alex():
    return signed_in_client("alex@silvercreek.example", "Canyon2026rapids")


def _check(token, tenant=SC):
    return api_post(Client(), "/auth/password-link/check", {"token": token}, tenant=tenant)


def _complete(token, password=NEW_PASSWORD, tenant=SC):
    return api_post(
        Client(),
        "/auth/password-link/complete",
        {"token": token, "new_password": password, "confirm_password": password},
        tenant=tenant,
    )


# ── creation ───────────────────────────────────────────────────────────────
def test_cr188__create_user_queues_an_invitation_with_a_link_and_no_password(mail):
    mail.seed_silvercreek()
    response = _add(_alex())
    assert response.status_code == 201
    body = response.json()
    temp = body["temp_password"]  # unchanged: still shown on screen (BR-IDN-022)
    assert body["invitation_email"] == {
        "status": "queued",
        "reason_code": None,
        "email": "tom@silvercreek.example",
    }
    (row,) = _rows()
    assert row.channel == nm.CHANNEL_EMAIL
    assert row.recipient_address == "tom@silvercreek.example"
    assert row.template_code == "staff_user_invite"
    assert row.priority == nm.PRIORITY_IMMEDIATE  # PO: "highest priority"
    context = row.render_context
    assert context["sign_in_link"].startswith(f"{ORIGIN}/{SC}/set-password#token=")
    assert context["username"] == "tom@silvercreek.example"
    assert context["utility_name"] == "Silver Creek Water"
    assert context["link_expires_on"]
    # ANSWER 1: no password anywhere in the queued message.
    flat = repr({f.name: getattr(row, f.name) for f in row._meta.fields})
    assert temp not in flat
    # Only a HASH is stored.
    token = _token(row)
    link = PasswordLink.objects.get()
    assert link.token_hash == password_links.hash_token(token)
    assert token not in repr(link.__dict__)
    assert link.expires_at == mail.clock() + timedelta(days=7)  # seeded setting
    assert "user.invitation_emailed" in mail.actions()


def test_cr188__no_provider_creates_the_user_and_says_not_sent(idn, settings):
    settings.PUBLIC_APP_ORIGIN = ORIGIN
    idn.seed_silvercreek()
    response = _add(_alex())
    assert response.status_code == 201  # the user is created regardless
    email = response.json()["invitation_email"]
    assert email["status"] == "not_sent"
    # Email dispatch ships OFF on a new utility, so the route says why.
    assert email["reason_code"] in {
        "email_sending_off",
        "provider_not_connected",
        "provider_status_unknown",
    }
    assert _rows() == []
    assert PasswordLink.objects.count() == 0  # no dead link minted
    assert User.objects.filter(email="tom@silvercreek.example").exists()
    (row,) = idn.rows_for("user.invitation_not_emailed")
    assert row["after"]["reason"] == email["reason_code"]


def test_cr188__no_public_address_is_not_sent_and_named(idn, settings, monkeypatch):
    settings.PUBLIC_APP_ORIGIN = ""  # law 3: fails closed
    monkeypatch.setattr(staff_access_events, "email_reachability", lambda: None)
    idn.seed_silvercreek()
    email = _add(_alex()).json()["invitation_email"]
    assert email == {
        "status": "not_sent",
        "reason_code": "public_address_not_configured",
        "email": "tom@silvercreek.example",
    }
    assert _rows() == []


# ── the link ───────────────────────────────────────────────────────────────
def test_cr188__the_link_sets_the_password_once_and_activates_the_membership(mail):
    mail.seed_silvercreek()
    _add(_alex())
    token = _token(_rows()[0])
    check = _check(token)
    assert check.status_code == 200
    assert check.json()["email"] == "tom@silvercreek.example"
    assert check.json()["password_policy"]["min_length"] == 8
    assert _complete(token).status_code == 204
    tom = User.objects.get(email="tom@silvercreek.example")
    assert TenantMembership.objects.get(user=tom).status == "active"  # BR-IDN-011
    assert tom.must_change_password is False
    assert api_sign_in(Client(), "tom@silvercreek.example", NEW_PASSWORD).status_code == 201
    # Single use.
    again = _complete(token, password="Another2026river")
    assert again.status_code == 409
    assert again.json()["message_key"] == "errors.identity.password_link_not_accepted"


def test_cr188__every_dead_link_gets_the_same_refusal(mail):
    mail.seed_silvercreek()
    _add(_alex())
    token = _token(_rows()[0])
    unknown = _check("not-a-real-token").json()
    mail.clock.advance(days=8)
    expired = _check(token).json()
    for body in (unknown, expired):
        assert body["message_key"] == "errors.identity.password_link_not_accepted"
        assert body["code"] == "BIZ-STATE"
    assert {k: v for k, v in unknown.items() if k != "trace_id"} == {
        k: v for k, v in expired.items() if k != "trace_id"
    }


def test_cr188__a_refused_password_does_not_spend_the_link(mail):
    mail.seed_silvercreek()
    _add(_alex())
    token = _token(_rows()[0])
    assert _complete(token, password="short").status_code == 422
    assert _complete(token).status_code == 204


def test_cr188__reset_voids_the_old_link_and_emails_a_new_one(mail):
    users = mail.seed_silvercreek()
    alex = _alex()
    _add(alex)
    old = _token(_rows()[0])
    tom = User.objects.get(email="tom@silvercreek.example")
    reset = api_post(alex, f"/users/{tom.id}/temp-password")
    assert reset.status_code == 200
    assert reset.json()["invitation_email"]["status"] == "queued"
    first, second = _rows()
    assert second.template_code == "staff_password_reset_link"
    assert reset.json()["temp_password"] not in repr(second.render_context)
    assert _check(old).status_code == 409
    assert _complete(_token(second)).status_code == 204
    assert users  # fixture used


def test_cr188__resend_invitation_is_for_invited_rows_and_voids_the_old_link(mail):
    users = mail.seed_silvercreek()
    alex = _alex()
    _add(alex)
    old = _token(_rows()[0])
    tom = User.objects.get(email="tom@silvercreek.example")
    resent = api_post(alex, f"/users/{tom.id}/resend-invitation")
    assert resent.status_code == 200
    body = resent.json()
    assert body["temp_password"] and body["invitation_email"]["status"] == "queued"
    assert _rows()[-1].template_code == "staff_user_invite"
    assert _check(old).status_code == 409
    assert _check(_token(_rows()[-1])).status_code == 200
    # An ACTIVE member has nothing to be invited to.
    refused = api_post(alex, f"/users/{users.priya.id}/resend-invitation")
    assert refused.status_code == 409


def test_cr188__a_password_chosen_another_way_voids_the_link(mail):
    mail.seed_silvercreek()
    response = _add(_alex())
    temp = response.json()["temp_password"]
    token = _token(_rows()[0])
    tom = signed_in_client("tom@silvercreek.example", temp)
    changed = api_post(
        tom, "/me/password", {"new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD}
    )
    assert changed.status_code == 204
    assert _check(token).status_code == 409


def test_cr188__a_link_from_one_utility_is_refused_on_another(mail):
    mail.seed_silvercreek()
    mail.seed_bluemesa_admin()
    _add(_alex())
    token = _token(_rows()[0])
    on_bm = _check(token, tenant=BM)
    assert on_bm.status_code == 409
    assert on_bm.json()["message_key"] == "errors.identity.password_link_not_accepted"


def test_cr188__link_life_is_the_utilitys_setting(mail):
    mail.seed_silvercreek()
    with core_tenancy.tenant_context(mail.silvercreek.id):
        SecurityPolicy.objects.update_or_create(
            tenant=mail.silvercreek, defaults={"password_link_valid_days": 3}
        )
    _add(_alex())
    link = PasswordLink.objects.get()
    assert link.expires_at == mail.clock() + timedelta(days=3)


# ── the templates ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("code", ["staff_user_invite", "staff_password_reset_link"])
def test_cr188__no_password_token_can_be_put_in_the_template(code):
    with pytest.raises(rendering.RenderRefused):
        rendering.validate_body(code, "Hi {staff_name}. {sign_in_link} {temp_password}")
    with pytest.raises(rendering.RenderRefused):  # the link is mandatory
        rendering.validate_body(code, "Hi {staff_name}.")
    klass = catalogs.catalog_for(code)
    assert not any("password" in token for token in klass.tokens)
    assert catalogs.LISTINGS[code].category == catalogs.CAT_ACCOUNT_ACCESS == "account_access"


def test_cr188__every_registry_language_is_seeded_natively_and_never_overwritten(mail):
    with core_tenancy.tenant_context(mail.silvercreek.id):
        seed_templates.ensure_seeded("staff_user_invite")
        languages = set(
            tm.NotificationTemplate.objects.filter(code="staff_user_invite").values_list(
                "language", flat=True
            )
        )
        registry = set(tenancy_seam.platform_languages())
        assert registry and languages == registry | {tm.VARIANT_DEFAULT}
        spanish = tm.NotificationTemplate.objects.get(code="staff_user_invite", language="es")
        live = tm.NotificationTemplateVersion.objects.get(template=spanish)
        assert live.body == account_access_wording.WORDING["staff_user_invite"]["es"][1]
        assert "{sign_in_link}" in live.body
        # A later release only ADDS: a variant that already has a published
        # version (the seed's, or the utility's own publish) gets nothing new.
        # (A published body is append-only on PostgreSQL — BR-BIL-026 — so a
        # utility's edit is always a NEW version, which this same check sees.)
        before = tm.NotificationTemplateVersion.objects.filter(
            template__code="staff_user_invite"
        ).count()
        seed_templates.ensure_seeded("staff_user_invite")
        assert (
            tm.NotificationTemplateVersion.objects.filter(template__code="staff_user_invite").count()
            == before
        )


def test_cr188__the_email_goes_out_in_the_utilitys_language(mail, monkeypatch):
    monkeypatch.setattr(tenancy_seam, "tenant_default_language", lambda: "es")
    mail.seed_silvercreek()
    _add(_alex())
    (row,) = _rows()
    assert row.template_language == "es"
    template = tm.NotificationTemplate.objects.get(pk=row.template_id)
    pinned = tm.NotificationTemplateVersion.objects.get(
        template=template, version=row.template_version
    )
    assert pinned.subject.startswith("Tu cuenta de")


# ── the whole path, as the browser walk found it (DEF-IDN-10366) ───────────
def test_cr188__the_invitation_is_sent_at_once_and_kept_with_the_link_redacted(
    mail, settings, monkeypatch, tmp_path, django_capture_on_commit_callbacks
):
    """Create user → the queue row → the instant job → the provider, with NO
    dispatch cycle; and the kept copy (BR-NOT-027, OQ-1164 *"keep them all"*)
    holds the redaction marker where the link was.

    DEF-IDN-10366: until the `account_access_email` kind existed, this row
    reached the freeze step and was refused `document_kind_not_ruled` — queued
    for ever. Every case above stubs the route and never dispatched, which is
    why only the browser walk saw it.
    """
    from apps.integrations import services as integrations_services
    from apps.notifications import dispatch_config, dispatcher, frozen_documents
    from apps.tenancy import document_store
    from core import jobs as core_jobs

    # The worker, in-process: whatever transport this run was configured with,
    # the job runs when it is dispatched (JOBS_EAGER's own transport).
    monkeypatch.setattr(core_jobs, "_dispatcher", core_jobs.run_eager)

    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    monkeypatch.setattr(
        integrations_services,
        "provider_connection_status",
        lambda channel: {"channel": channel, "connected": True, "provider_key": "stub"},
        raising=False,
    )
    handed = []

    def adapter(channel, messages):
        handed.extend(messages)
        return {m["id"]: {"status": "sent", "provider_reference": "stub"} for m in messages}

    monkeypatch.setattr(integrations_services, "dispatch_outbound_batch", adapter, raising=False)
    monkeypatch.setattr(dispatcher, "dispatch_cycle", lambda **kw: pytest.fail("no cycle"))
    mail.seed_silvercreek()
    with core_tenancy.tenant_context(mail.silvercreek.id):
        # The utility has switched email sending on (Settings → Notifications).
        dispatch_config.dispatch_settings()  # materialises the row
        nm.NotificationSettings.objects.filter(tenant_id=mail.silvercreek.id).update(
            email_dispatch_active=True
        )
    with django_capture_on_commit_callbacks(execute=True):
        response = _add(_alex())
    assert response.json()["invitation_email"]["status"] == "queued"
    (row,) = _rows()
    row.refresh_from_db()
    assert row.status == nm.STATUS_SENT  # sent at once, no cycle
    link = row.render_context["sign_in_link"]
    (message,) = handed
    assert link in repr(message)  # the live email carries the real link
    media, _ext = frozen_documents.ARTEFACT_MEDIA[row.channel]
    with core_tenancy.tenant_context(mail.silvercreek.id):
        kept = document_store.for_source(
            source_type=frozen_documents.STORE_SOURCE_TYPE,
            source_id=row.pk,
            channel=row.channel,
            content_type=media,
        )
        assert kept.found and kept.document.kind == "account_access_email"
        body = document_store.fetch(kept.document.id).decode("utf-8")
    assert frozen_documents.REDACTION_MARKER in body
    assert link not in body and _token(row) not in body
    assert response.json()["temp_password"] not in body

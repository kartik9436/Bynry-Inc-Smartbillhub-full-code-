# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-CWP-10380 (a blank or malformed address answered 200 "check your
#           inbox") · DEF-CWP-10381 (the reset email was never sent: no
#           wording, no link, no page to use it on). PO report 2026-10-22.
# Story:    US-CWP-020 (CWP-019) — forgotten password · TC-1..TC-7
# Rules:    BR-CWP-038 (the same answer for every well-formed address — it
#           STANDS, PO ruling 2026-10-22) · PO 2026-10-22 *"instant email"* and
#           *"don't do any hardcoding"* · OQ-CUS-12619 (a message goes in the
#           utility's language) · hard rule 1 (tenant scoping)
# Tests:    this file — SQLite and `--ds=config.settings.pgtest`
# ───────────────────────────────────────────────────────
"""The portal reset, end to end, through HTTP and the dispatcher's own render.

What earlier tests asked was *was something queued?*, and the answer was yes
while every row held at dispatch for want of wording. So the known-address case
here renders the queued row through `rendering.render_for_dispatch` — the path
the dispatcher uses — and then follows the link it printed.
"""

from __future__ import annotations

import json
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from django.test import Client
from django.utils import timezone

from apps.notifications import account_access_wording, catalogs, frozen_documents, rendering
from apps.notifications import models as notification_models
from apps.notifications import template_models as tm
from apps.portal import api as portal_api
from apps.portal import credentials
from apps.portal import models as portal_models
from apps.portal.seams import identity_seam as portal_identity_seam
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import MARIA_EMAIL, MARIA_PASSWORD, enrol_maria, switch_on

ORIGIN = "https://app.example.test"
WORDS = account_access_wording.WORDING["portal_password_reset"]
NEW_PASSWORD = "Harbor-2026-tide"


@pytest.fixture(autouse=True)
def public_origin(settings):
    settings.PUBLIC_APP_ORIGIN = ORIGIN


@pytest.fixture()
def sent_now(monkeypatch):
    """Every id handed to `notifications.services.send_now` — the instant
    sender the staff-invite lane owns. Patched in whether or not it exists on
    this base, because the portal resolves it by name."""
    from apps.notifications import services

    calls: list[list] = []
    monkeypatch.setattr(
        services, "send_now", lambda ids, **kw: calls.append([str(i) for i in ids]), raising=False
    )
    return calls


def post(tenant, path: str, body, client: Client | None = None):
    return (client or Client()).post(
        f"/api/{tenant.subdomain}/portal/{path}",
        data=json.dumps(body),
        content_type="application/json",
    )


def portal_rows(tenant):
    with tenant_context(tenant.id):
        return list(notification_models.OutboundMessage.objects.filter(source_type="portal"))


def reset_codes(tenant):
    with tenant_context(tenant.id):
        return portal_models.PortalOneTimeCode.objects.filter(
            purpose=portal_models.PURPOSE_RESET
        ).count()


def live(tenant, actor):
    switch_on(tenant, actor)
    return enrol_maria(tenant, actor)


def ref_and_token(link: str) -> tuple[str, str]:
    # Both halves travel in the FRAGMENT (decision log 2026-10-22, MERGE-ACCESS).
    parts = urlsplit(link)
    assert parts.query == "", "a one-time secret in the query string reaches server logs"
    fragment = parse_qs(parts.fragment)
    return fragment["ref"][0], fragment["token"][0]


# ══ DEF-CWP-10380 · what is not an address is refused, and discloses nothing ══


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ({"email": ""}, "email_required"),
        ({"email": "   "}, "email_required"),
        ({}, "email_required"),
        ({"email": None}, "email_required"),
        ({"email": "not-an-email"}, "email_invalid"),
        ({"email": "maria@"}, "email_invalid"),
        ({"email": "two words@example.test"}, "email_invalid"),
    ],
)
def test_a_blank_or_malformed_address_is_400_and_nothing_is_minted(pine_hill, sarah, body, reason):
    live(pine_hill, sarah)
    answer = post(pine_hill, "auth/forgot-password", body)
    assert answer.status_code == 400, answer.content
    assert answer.json()["reason"] == reason
    assert answer.json()["message_key"] == f"portal.reset.{reason}"
    assert reset_codes(pine_hill) == 0
    assert portal_rows(pine_hill) == []


# ══ BR-CWP-038 STANDS — one answer for every well-formed address ════════════


@pytest.mark.django_db
def test_known_and_unknown_answer_byte_identical_and_only_known_gets_mail(
    pine_hill, sarah, sent_now, monkeypatch
):
    live(pine_hill, sarah)
    spent: list[str] = []
    real = credentials.equalise_timing
    monkeypatch.setattr(credentials, "equalise_timing", lambda: (spent.append("x"), real())[1])

    unknown = post(pine_hill, "auth/forgot-password", {"email": "nobody@example.test"})
    assert portal_rows(pine_hill) == [], "an unknown address queued an email"
    assert sent_now == []
    assert spent == ["x"]

    known = post(pine_hill, "auth/forgot-password", {"email": MARIA_EMAIL})
    assert unknown.status_code == known.status_code == 200
    assert unknown.content == known.content, "BR-CWP-038: the two answers differ"
    # The SAME timing work on both branches: one password-hash check each, so a
    # registered address cannot answer ~100 ms faster than an unknown one.
    assert spent == ["x", "x"]
    rows = portal_rows(pine_hill)
    assert len(rows) == 1
    # Instant send (PO 2026-10-22): handed over with the id of the row just queued.
    assert sent_now == [[str(rows[0].id)]]


# ══ DEF-CWP-10381 · the email exists, renders, and its link works ═══════════


@pytest.mark.django_db
def test_the_queued_email_renders_with_the_link_and_the_link_sets_a_password(
    pine_hill, sarah, sent_now
):
    live(pine_hill, sarah)
    post(pine_hill, "auth/forgot-password", {"email": MARIA_EMAIL})
    (row,) = portal_rows(pine_hill)
    assert row.channel == notification_models.CHANNEL_EMAIL
    assert row.template_code == "portal_password_reset"
    assert row.template_id is not None and row.template_version is not None, (
        "the row carries no pin: it would hold at dispatch and never be sent"
    )
    link = row.render_context["reset_link"]
    assert link.startswith(f"{ORIGIN}/{pine_hill.subdomain}/portal/forgot-password#")
    with tenant_context(pine_hill.id):
        rendered = rendering.render_for_dispatch(row)
        # ⚠ THE DISPATCHER'S FREEZE STEP MUST LET IT GO. A class with no
        # document kind HOLDS there forever (`FREEZE_KIND_UNRULED`). It is KEPT
        # like every document (OQ-1164) — with the link REDACTED in the kept
        # copy, so the seven-year record holds no usable credential.
        frozen = frozen_documents.freeze_for_dispatch(row, rendered, moment=timezone.now())
        assert frozen.may_send and not frozen.exempt, frozen
        assert frozen.document is not None and frozen.document.kind == "account_access_email"
        kept = frozen_documents.redact_credentials(
            row, frozen_documents.artefact_bytes(row, rendered)[0]
        )
        from apps.tenancy import document_storage

        # What was STORED is exactly the redacted copy, byte for byte.
        assert frozen.document.content_hash == document_storage.content_hash(kept)
        kept = kept.decode("utf-8")
    assert link not in kept and frozen_documents.REDACTION_MARKER in kept
    assert ref_and_token(link)[1] not in kept, "the kept copy holds the live token"
    assert link in rendered.body
    assert rendered.subject and "——" not in rendered.subject
    assert rendered.absences == () or all(
        a["token"] not in {"reset_link", "customer_name"} for a in rendered.absences
    )
    assert row.render_context["customer_name"] in rendered.body

    ref, token = ref_and_token(link)
    # A password the policy refuses does NOT spend the link.
    weak = post(pine_hill, "auth/reset-password", {"ref": ref, "token": token, "password": "short"})
    assert weak.status_code == 422 and weak.json()["message_key"] == "portal.reset.policy"
    good = post(
        pine_hill, "auth/reset-password", {"ref": ref, "token": token, "password": NEW_PASSWORD}
    )
    assert good.status_code == 200, good.content
    signed_in = post(pine_hill, "auth/sign-in", {"email": MARIA_EMAIL, "password": NEW_PASSWORD})
    assert signed_in.status_code == 200, signed_in.content
    old = post(pine_hill, "auth/sign-in", {"email": MARIA_EMAIL, "password": MARIA_PASSWORD})
    assert old.status_code == 401
    # Single use (TC-6).
    again = post(
        pine_hill,
        "auth/reset-password",
        {"ref": ref, "token": token, "password": NEW_PASSWORD + "x"},
    )
    assert again.status_code == 422 and again.json()["reason"] == "wrong"


@pytest.mark.django_db
def test_an_expired_link_is_refused_as_expired(pine_hill, sarah, sent_now):
    live(pine_hill, sarah)
    post(pine_hill, "auth/forgot-password", {"email": MARIA_EMAIL})
    (row,) = portal_rows(pine_hill)
    ref, token = ref_and_token(row.render_context["reset_link"])
    with tenant_context(pine_hill.id):
        portal_models.PortalOneTimeCode.objects.filter(pk=ref).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
    answer = post(
        pine_hill, "auth/reset-password", {"ref": ref, "token": token, "password": NEW_PASSWORD}
    )
    assert answer.status_code == 422
    assert answer.json()["message_key"] == "portal.reset.link.expired"


@pytest.mark.django_db
def test_the_lifetime_is_the_utilitys_setting_not_a_constant(
    pine_hill, sarah, sent_now, monkeypatch
):
    live(pine_hill, sarah)
    monkeypatch.setattr(portal_identity_seam, "password_link_valid_days", lambda tenant_id: 2)
    before = timezone.now()
    post(pine_hill, "auth/forgot-password", {"email": MARIA_EMAIL})
    with tenant_context(pine_hill.id):
        code = portal_models.PortalOneTimeCode.objects.get(purpose=portal_models.PURPOSE_RESET)
    assert (
        timedelta(days=2) - timedelta(minutes=1)
        < code.expires_at - before
        <= timedelta(days=2, minutes=1)
    )


@pytest.mark.django_db
def test_a_pine_hill_link_is_refused_under_oak_ridge(pine_hill, oak_ridge, sarah, sent_now):
    live(pine_hill, sarah)
    post(pine_hill, "auth/forgot-password", {"email": MARIA_EMAIL})
    (row,) = portal_rows(pine_hill)
    ref, token = ref_and_token(row.render_context["reset_link"])
    answer = post(
        oak_ridge, "auth/reset-password", {"ref": ref, "token": token, "password": NEW_PASSWORD}
    )
    assert answer.status_code in (404, 422)
    # And the link still works where it belongs: the refusal spent nothing.
    home = post(
        pine_hill, "auth/reset-password", {"ref": ref, "token": token, "password": NEW_PASSWORD}
    )
    assert home.status_code == 200


@pytest.mark.django_db
def test_no_public_address_sends_nothing_says_the_same_and_records_why(
    pine_hill, sarah, sent_now, settings, audit_rows
):
    live(pine_hill, sarah)
    settings.PUBLIC_APP_ORIGIN = ""
    known = post(pine_hill, "auth/forgot-password", {"email": MARIA_EMAIL})
    unknown = post(pine_hill, "auth/forgot-password", {"email": "nobody@example.test"})
    assert known.status_code == 200 and known.content == unknown.content
    assert portal_rows(pine_hill) == []
    assert reset_codes(pine_hill) == 0, "a code was minted for a link nobody was sent"
    assert sent_now == []
    (audit,) = [row for row in audit_rows if row["action"] == "portal_credential.reset_not_sent"]
    assert "public address is not configured" in audit["after"]["reason"]


@pytest.mark.django_db
def test_the_email_goes_in_the_utilitys_language(pine_hill, sarah, sent_now):
    live(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        tenancy_models.TenantSettings.objects.filter(tenant_id=pine_hill.id).update(
            language="es-MX"
        )
    post(pine_hill, "auth/forgot-password", {"email": MARIA_EMAIL})
    (row,) = portal_rows(pine_hill)
    assert row.template_language == "es-MX"
    with tenant_context(pine_hill.id):
        rendered = rendering.render_for_dispatch(row)
    assert "Restablece tu contraseña" in (rendered.subject or "")
    assert row.render_context["reset_link"] in rendered.body


@pytest.mark.django_db
def test_rate_limits_on_the_reset_routes_are_unchanged():
    for view in (portal_api.forgot_password, portal_api.reset_password):
        names = {klass.__name__ for klass in view.cls.throttle_classes}
        assert {"PublicOnboardingThrottle", "PortalTenantThrottle"} <= names


# ══ The template: catalogue, palette, seeding ═════════════════════════════


def test_the_class_is_listed_under_account_access_with_its_palette():
    listing = catalogs.listing_for("portal_password_reset")
    assert listing.category == catalogs.CAT_ACCOUNT_ACCESS == "account_access"
    assert listing.name == "Customer Portal Password Reset Link"
    klass = catalogs.catalog_for("portal_password_reset")
    assert {"customer_name", "utility_name", "reset_link"} <= klass.tokens
    assert catalogs.used_by_state("portal_password_reset") == catalogs.USED_BY_IN_USE


def test_validation_refuses_an_unknown_token_and_a_body_without_the_link():
    with pytest.raises(Exception, match="meter_no"):
        rendering.validate_body("portal_password_reset", "Hi {meter_no} {reset_link}")
    with pytest.raises(Exception):
        rendering.validate_body("portal_password_reset", "Hi {customer_name}, no link here")
    subject, body = WORDS["en"]
    rendering.validate_body("portal_password_reset", body, subject=subject)


def test_every_variant_passes_the_palette_and_carries_the_link():
    for language, (subject, body) in WORDS.items():
        rendering.validate_body("portal_password_reset", body, subject=subject)
        assert "{reset_link}" in body, language


def test_every_non_english_product_language_has_a_native_variant():
    """The registry, not a list typed here: a language the product adds without
    a variant makes this red (it would otherwise read English silently)."""
    missing = [
        code
        for code in tenancy_services.SEED_LANGUAGES
        if account_access_wording.wording_for("portal_password_reset", code) is None
    ]
    assert missing == []


@pytest.mark.django_db
def test_a_new_utility_is_seeded_with_every_variant_published(pine_hill):
    with tenant_context(pine_hill.id):
        languages = set(
            tm.NotificationTemplateVersion.objects.filter(
                template__code="portal_password_reset", status=tm.VERSION_PUBLISHED
            ).values_list("template__language", flat=True)
        )
    assert languages == {"default", *tenancy_services.SEED_LANGUAGES}


@pytest.mark.django_db
def test_the_data_migration_adds_only_missing_variants_and_is_idempotent(pine_hill, monkeypatch):
    """A released language a utility lacks is ADDED; every variant it already
    publishes is left byte-for-byte alone; a second run writes nothing.

    The 'missing' variant is a new language added to the registry rather than
    a deleted row, because published versions cannot be deleted on PostgreSQL
    (`trg_ntv_append_only`) — which is also the honest shape of the case: a
    later release ADDS a language."""
    import importlib

    from django.apps import apps as django_apps

    migration = importlib.import_module(
        "apps.notifications.migrations.0023_cr188_priority_and_account_access"
    )
    monkeypatch.setattr(
        tenancy_services, "SEED_LANGUAGES", (*tenancy_services.SEED_LANGUAGES, "xx-TEST")
    )
    monkeypatch.setitem(WORDS, "xx-TEST", WORDS["en"])

    def snapshot():
        with tenant_context(pine_hill.id):
            return sorted(
                tm.NotificationTemplateVersion.objects.filter(
                    template__code="portal_password_reset"
                ).values_list("template__language", "version", "body")
            )

    before = snapshot()
    migration.plant_account_access(django_apps, None)
    after = snapshot()
    added = [row for row in after if row not in before]
    assert [(language, version) for language, version, _ in added] == [("xx-TEST", 1)]
    assert set(before) <= set(after), "an existing variant was changed"
    migration.plant_account_access(django_apps, None)
    assert snapshot() == after, "a second run wrote something"

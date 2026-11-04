# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-10531 — the bill-ready email said "it is attached to this
#           email" and nothing was attached
# Ruling:   PO 2026-10-22 (*"can't we sent link instead"*, then *"b direct PDF
#           link"*); lane BILL-LINK's judgments in the decision log entry after
# Rules:    BR-NOT-027 (the KEPT PDF) · CLAUDE.md hard rules 1, 4, 7 · law 3 ·
#           decision log 2026-10-22 "One-time link secrets travel in the URL
#           FRAGMENT"
# Tests:    this file (sqlite) · test_def_bil_10531_bill_link_pg.py (PostgreSQL)
# ───────────────────────────────────────────────────────
"""The bill email carries a secret, expiring link that opens the bill's kept PDF.

REPRODUCED BEFORE THE FIX (law 7): the bill-ready email rendered *"Your bill for
… is ready, and it is attached to this email."* and the SendGrid payload carried
no `attachments` key at all.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
  * **A token read off the database.** Only the digest is stored, so every case
    takes the token from the LINK in the queued email's render context — the
    one place a customer gets it.
  * **"Opens the PDF" proved against a fresh render.** The bytes are compared
    with the KEPT PDF from the document store, byte for byte.
  * **An expiry asserted against a constant.** The setting is moved to 3 days
    and the expiry is asserted against that.
  * **"Refused" passing on any answer.** Every refusal asserts the exact body
    `{"state": "unavailable", ...}`, identical for unknown, expired and foreign.
  * **"Not in the URL" asserted on our own string.** The URL patterns are read
    from the wired URLconf, and a GET carrying the token in the query is shown
    to open nothing.

RUN WITH `JOBS_EAGER=false --reuse-db` (DEF-567).
"""

from __future__ import annotations

import json
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from django.test import Client
from django.urls import get_resolver
from django.utils import timezone

from apps.billing import bill_links, frozen_bill
from apps.billing import models as billing_models
from apps.billing.bill_link_models import BillLink
from apps.notifications import bill_email_wording, rendering, seed_templates
from apps.notifications import models as outbound
from apps.tenancy import document_store
from core import link_tokens
from tests.test_def_bil_10530_bill_email_pin import (  # noqa: F401 — fixtures
    INSIDE_WINDOW,
    _email_contact,
    sendgrid,
)
from tests.test_otb_a_one_time_api_contract import (  # noqa: F401 — autouse fixture
    _a_fee_draft,
    _clerk,
    _send,
    _the_unit_bills_on_a_cycle,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · lonestar
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ORIGIN = "https://app.example.test"


@pytest.fixture(autouse=True)
def _env(settings, tmp_path):
    settings.PUBLIC_APP_ORIGIN = ORIGIN
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")


def _issued(tenant, actor):
    """A real one-time bill, issued through the shipped Send, with an email."""
    user = _clerk(tenant)
    draft = _a_fee_draft(tenant, actor, user)
    with tenant_ctx(tenant):
        invoice = billing_models.Invoice.objects.get(pk=draft["invoice_id"])
        _email_contact(tenant, invoice.account_id)
    sent = _send(tenant, user, draft["run_id"])
    assert sent.status_code == 201, sent.data
    with tenant_ctx(tenant):
        invoice.refresh_from_db()
        email = outbound.OutboundMessage.objects.get(source_id=invoice.pk, channel="email")
    return invoice, email


def _link(email) -> str:
    return rendering.decode_context(email.render_context)["bill_link"]


def _token(link: str) -> str:
    parts = urlsplit(link)
    assert f"{parts.scheme}://{parts.netloc}" == ORIGIN
    assert parts.query == "", "the secret must never ride in the query string"
    return parse_qs(parts.fragment)["token"][0]


def _post(tenant, door, token):
    return Client().post(
        f"/api/{tenant.subdomain}/bill-links/{door}",
        data=json.dumps({"token": token}),
        content_type="application/json",
    )


def _kept_pdf(tenant, invoice) -> bytes:
    with tenant_ctx(tenant):
        reproduction = frozen_bill.reproduce(invoice)
        assert reproduction.is_original
        return document_store.fetch(reproduction.pdf.id)


# ── 1 · the email carries the link ───────────────────────────────────────────


def test_the_bill_email_body_carries_the_link_and_no_attachment_promise(brazos, dana, sendgrid):
    from apps.notifications import dispatcher

    invoice, email = _issued(brazos, dana)
    link = _link(email)
    token = _token(link)
    assert urlsplit(link).path == f"/{brazos.subdomain}/portal/bill"
    with tenant_ctx(brazos):
        row = BillLink.objects.get(invoice_id=invoice.pk)
        # Only the digest is kept.
        assert row.token_hash == link_tokens.digest(token)
        assert token not in json.dumps(list(BillLink.objects.values()), default=str)
        dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(outbound.CHANNEL_EMAIL,))
        email.refresh_from_db()
        assert email.status == outbound.STATUS_SENT, (email.status, email.last_error)
    sends = [one for one in sendgrid.sent if one[1].endswith("/v3/mail/send")]
    assert len(sends) == 1
    text = sends[0][3]["content"][0]["value"]
    assert link in text, text
    assert "attached" not in text.lower(), text
    assert "This link works until" in text


def test_the_kept_copy_of_the_email_has_the_link_removed():
    from apps.notifications import catalogs

    for code in (bill_email_wording.BILL_READY, bill_email_wording.CORRECTED_BILL):
        klass = catalogs.catalog_for(code)
        assert "bill_link" in klass.credential_tokens, code
        assert {"bill_link", "link_expires_on"} <= klass.optional, code


# ── 2 · the link opens the KEPT PDF, byte for byte ───────────────────────────


def test_the_link_opens_the_frozen_pdf_byte_for_byte_and_audits_each_open(brazos, dana, audit_rows):
    invoice, email = _issued(brazos, dana)
    token = _token(_link(email))
    kept = _kept_pdf(brazos, invoice)

    page = _post(brazos, "open", token)
    assert page.status_code == 200
    assert page.json()["state"] == "open"
    assert page.json()["bill_no"] == invoice.invoice_no
    assert page["Cache-Control"].startswith("no-store")

    for _ in range(2):  # judgment 3: open it as often as you like
        document = _post(brazos, "document", token)
        assert document.status_code == 200
        assert document["Content-Type"] == "application/pdf"
        assert document.content == kept

    with tenant_ctx(brazos):
        row = BillLink.objects.get(invoice_id=invoice.pk)
    trail = [r for r in audit_rows if r["entity_type"] == "bill_link"]
    assert {str(r["entity_id"]) for r in trail} == {str(row.pk)}
    # The bill and nothing about who opened it (judgment 3).
    assert all(r["after"]["invoice_id"] == str(invoice.pk) for r in trail)
    assert all(r.get("actor_user_id") is None for r in trail)
    actions = sorted(r["action"] for r in trail)
    assert actions == [
        bill_links.AUDIT_DOWNLOADED,
        bill_links.AUDIT_DOWNLOADED,
        bill_links.AUDIT_OPENED,
    ]


# ── 3 · expired, unknown, foreign — one refusal ──────────────────────────────


def test_an_expired_an_unknown_and_another_utilitys_link_all_refuse_alike(brazos, dana, lonestar):
    invoice, email = _issued(brazos, dana)
    token = _token(_link(email))

    unknown = _post(brazos, "document", link_tokens.mint())
    assert unknown.status_code == 200
    assert unknown.json()["state"] == "unavailable"
    assert "support_phone" in unknown.json()

    # Another utility's address: neither door answers with brazos's bill. The
    # page door is the sharp one — the PDF door would also be stopped one step
    # later by the document store's own tenant filter, which is defence in
    # depth and not the guard under test (proved: a lookup that ignored the
    # tenant passed a document-only check).
    for door in ("open", "document"):
        foreign = _post(lonestar, door, token)
        assert foreign.status_code == 200
        assert foreign.json() == {
            "state": "unavailable",
            "support_phone": foreign.json()["support_phone"],
        }, door

    with tenant_ctx(brazos):
        BillLink.objects.filter(invoice_id=invoice.pk).update(
            issued_at=timezone.now() - timedelta(days=40),
            expires_at=timezone.now() - timedelta(seconds=1),
        )
    expired_page = _post(brazos, "open", token)
    expired_pdf = _post(brazos, "document", token)
    assert expired_page.json() == unknown.json()
    assert expired_pdf.json() == unknown.json()
    assert expired_pdf["Content-Type"].startswith("application/json")


# ── 4 · the setting moves the expiry ─────────────────────────────────────────


def test_the_link_life_is_the_utility_setting_not_a_constant(brazos, dana):
    from apps.portal import models as portal_models

    _first, email = _issued(brazos, dana)
    with tenant_ctx(brazos):
        row = BillLink.objects.get(invoice_id=_first.pk)
        assert (row.expires_at - row.issued_at) == timedelta(days=30)
        portal_models.PortalSettings.objects.update_or_create(
            tenant_id=brazos.id, defaults={"bill_link_valid_days": 3}
        )
        moved, problems = bill_links.mint(_first)
        assert problems == ()
        newest = BillLink.objects.filter(invoice_id=_first.pk).exclude(pk=row.pk).get()
        assert (newest.expires_at - newest.issued_at) == timedelta(days=3)
        assert (
            moved["link_expires_on"]
            == newest.expires_at.astimezone(bill_links.bill_link_seam.tenant_timezone()).date()
        )


def test_the_setting_is_saved_through_settings_customer_portal_with_its_bounds(brazos, dana):
    from apps.portal import settings_service
    from core import errors

    with tenant_ctx(brazos):
        saved = settings_service.save_settings(dana, brazos.id, {"bill_link_valid_days": 14})
        assert saved["bill_link_valid_days"] == 14
        with pytest.raises(errors.ValidationError):
            settings_service.save_settings(dana, brazos.id, {"bill_link_valid_days": 0})
        with pytest.raises(errors.ValidationError):
            settings_service.save_settings(dana, brazos.id, {"bill_link_valid_days": 91})


def test_no_public_address_means_no_link_and_the_bill_still_issues(brazos, dana, settings):
    settings.PUBLIC_APP_ORIGIN = ""
    invoice, email = _issued(brazos, dana)
    assert _link(email) is None
    with tenant_ctx(brazos):
        assert not BillLink.objects.filter(invoice_id=invoice.pk).exists()


# ── 5 · the secret is never in a request URL ─────────────────────────────────


def test_no_bill_link_route_takes_the_token_in_its_address(brazos, dana):
    from apps.billing import bill_link_public_api as edge

    for pattern in edge.urlpatterns:
        assert "<" not in str(pattern.pattern), pattern.pattern
    # The wired URLconf resolves both doors, POST only.
    resolver = get_resolver()
    for door in ("open", "document"):
        match = resolver.resolve(f"/api/{brazos.subdomain}/bill-links/{door}")
        assert match.func.cls.http_method_names  # DRF view
    invoice, email = _issued(brazos, dana)
    token = _token(_link(email))
    leaked = Client().get(f"/api/{brazos.subdomain}/bill-links/document", {"token": token})
    assert leaked.status_code == 405


# ── 6 · the wording ──────────────────────────────────────────────────────────


def test_both_bill_emails_drop_the_attachment_sentence_in_every_language():
    for code, languages in bill_email_wording.WORDING.items():
        assert len(languages) == 11, code
        for language, (subject, body) in languages.items():
            assert "{bill_link}" in body and "{link_expires_on}" in body, (code, language)
            paragraph = next(p for p in body.split("\n\n") if "{bill_link}" in p)
            assert "{link_expires_on}" in paragraph, (code, language)
            assert len([p for p in body.split("\n\n") if "{bill_link}" in p]) == 1
            assert "attach" not in body.lower(), (code, language)
            rendering.validate_body(code, body, subject=subject)
    assert (
        seed_templates.EMAIL_BILL_READY_BODY
        == bill_email_wording.WORDING[bill_email_wording.BILL_READY]["en"][1]
    )


def test_the_migration_moves_only_an_unedited_default_and_its_new_text_is_the_seed():
    migration = __import__(
        "apps.notifications.migrations.0030_def_bil_10531_bill_email_link_wording",
        fromlist=["CHANGES"],
    )
    for code, (subject, old, new) in migration.CHANGES.items():
        assert (subject, new) == bill_email_wording.WORDING[code]["en"], code
        assert "attached" in old and "attached" not in new, code


def test_the_migration_republishes_an_unedited_default_and_leaves_an_edited_one(brazos, dana):
    from django.apps import apps as django_apps

    from apps.notifications import template_models as tm
    from apps.notifications import template_service

    migration = __import__(
        "apps.notifications.migrations.0030_def_bil_10531_bill_email_link_wording",
        fromlist=["republish", "CHANGES"],
    )
    now = timezone.now()
    with tenant_ctx(brazos):
        for code, (subject, old, _new) in migration.CHANGES.items():
            template = tm.NotificationTemplate.objects.get(
                code=code, category=tm.VARIANT_DEFAULT, language=tm.VARIANT_DEFAULT
            )
            live = template.versions.filter(status="published").order_by("-version").first()
            body = old if code == bill_email_wording.BILL_READY else old + "\n(edited)"
            draft = template_service.save_draft(
                template=template, body=body, actor=dana, subject=subject
            )
            template_service.publish(version_row=draft, actor=dana)
            assert live is not None
        moved = {
            code: migration.republish(django_apps, brazos.id, now, code)
            for code in migration.CHANGES
        }
    assert moved == {bill_email_wording.BILL_READY: 1, bill_email_wording.CORRECTED_BILL: 0}

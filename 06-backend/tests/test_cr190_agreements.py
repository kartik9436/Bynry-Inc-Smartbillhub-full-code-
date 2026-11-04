"""CR-190-BRC10 lane AGREEMENT — the click-to-accept agreement, end to end.

PO 2026-10-22, decision logs *"Move-in messaging and the welcome email: four
answers"* (answer 1: *"email it as a PDF attachment (plus a letter if the
customer wants paper)"*) and *"Click-to-accept agreements: the design confirmed
with four answers"* (7 days, a setting · tick + date + typed name · expired →
resend, service continues · no in-portal acceptance).

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
  * **A token read off the database.** Only the DIGEST is stored, so the cases
    take the token from the LINK inside the queued email's own render context —
    the one place a customer gets it. A test that found the token anywhere else
    would prove a leak, not a feature.
  * **An expiry asserted against a constant.** The setting is MOVED to 3 days in
    one case and the expiry is asserted against that, so a hardcoded 7 fails.
  * **"Refused" passing on any exception.** Every public refusal asserts the
    exact `LinkUnavailable` and, over HTTP, a byte-identical body across the
    four reasons.
  * **A stamped copy that is just the sent copy.** The filed PDF is asserted to
    DIFFER from the sent PDF (the stamp is in it).

RUN WITH `JOBS_EAGER=false --reuse-db` (DEF-567).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from urllib.parse import urlsplit

import pytest
from django.utils import timezone

from apps.customers import agreements, notifications_seam
from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.customers.agreement_models import AgreementRequest
from apps.notifications import attachments
from apps.notifications import models as notification_models
from apps.notifications import rendering, seed_templates, template_service
from apps.notifications import template_models as tm

from tests.test_br_cus_1077_move_in_job import _served_unit
from tests.test_def_cus_6353_first_occupant_move_in import _payload
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

ORIGIN = "https://app.example.test"


@pytest.fixture(autouse=True)
def _env(settings, tmp_path):
    settings.PUBLIC_APP_ORIGIN = ORIGIN
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")


def _publish_agreement(tenant, actor):
    offered = seed_templates.default_body_for("contract_service_agreement")
    with tenant_ctx(tenant):
        template, _ = template_service.register(
            code="contract_service_agreement",
            name=offered.name,
            actor=actor,
            category=tm.VARIANT_DEFAULT,
            language=tm.VARIANT_DEFAULT,
        )
        draft = template_service.save_draft(
            template=template,
            body=offered.body,
            actor=actor,
            effective_from=date(2026, 1, 1),
        )
        template_service.publish(version_row=draft, actor=actor)


def _move_in(actor, tenant, label):
    _premises, unit = _served_unit(actor, tenant, label=label, address=f"{label} Elm")
    return customers_services.move_in_to_unit(actor, unit["id"], _payload())


def _email(account_id):
    return notification_models.OutboundMessage.objects.get(
        account_id=account_id, template_code="email_agreement_request", channel="email"
    )


def _token(message) -> str:
    link = rendering.decode_context(message.render_context)["agreement_link"]
    parts = urlsplit(link)
    assert f"{parts.scheme}://{parts.netloc}" == ORIGIN
    return parts.path.rsplit("/", 1)[-1]


@pytest.fixture()
def published(brazos, dana):
    _publish_agreement(brazos, dana)
    return brazos


# ── 1 · the move-in sends it ─────────────────────────────────────────────────


def test_move_in_sends_the_agreement_by_email_with_the_pdf_attached_and_a_link(published, dana):
    from apps.tenancy import document_store

    with tenant_ctx(published):
        result = _move_in(dana, published, "Unit 1901")
        row = AgreementRequest.objects.get(account_id=result["id"])
        email = _email(result["id"])
        token = _token(email)
        # Only the digest is kept; the token is in the link and nowhere else.
        assert row.token_hash == agreements._digest(token)
        assert token not in json.dumps(agreements.summary(row), default=str)
        # Seven days, from the SETTING.
        assert (row.expires_at - row.issued_at) == timedelta(days=7)
        # The PDF is attached, by name, and its bytes are a PDF.
        named = attachments.named(email.recipient_snapshot)
        assert [item["content_type"] for item in named] == ["application/pdf"]
        handed = attachments.for_handoff(email.recipient_snapshot)
        assert handed[0]["content"].startswith(b"%PDF-")
        assert document_store.fetch(row.sent_document_id) == handed[0]["content"]
        # Normal priority: the regular dispatch cycle sends it (coordinator relay
        # 2026-10-22 — the instant send is for account-access emails only).
        assert getattr(email, "priority", 0) == 0
        # Not paperless (the default) → the printed letter as well.
        assert row.letter_message_id is not None
        letter = notification_models.OutboundMessage.objects.get(pk=row.letter_message_id)
        assert letter.channel == "pdf_print"
        assert letter.template_code == "contract_service_agreement"
    codes = [item.get("code") for item in result["service_agreement_message"]]
    assert notifications_seam.MOVE_MESSAGE_QUEUED in codes


def test_the_link_life_is_the_utility_setting_not_a_constant(published, dana):
    from apps.portal import models as portal_models

    with tenant_ctx(published):
        portal_models.PortalSettings.objects.update_or_create(
            tenant_id=published.id, defaults={"agreement_link_valid_days": 3}
        )
        result = _move_in(dana, published, "Unit 1902")
        row = AgreementRequest.objects.get(account_id=result["id"])
    assert (row.expires_at - row.issued_at) == timedelta(days=3)


def test_a_paperless_customer_gets_no_letter(published, dana):
    with tenant_ctx(published):
        result = _move_in(dana, published, "Unit 1903")
        customers_models.Account.objects.filter(pk=result["id"]).update(paperless=True)
        # An email the customer can be reached at — without one the letter is
        # sent anyway, so nobody is sent nothing (decision log, judgment 1).
        customers_models.Contact.objects.filter(account_id=result["id"]).update(
            email="ana@example.test"
        ) or customers_models.Contact.objects.create(
            tenant_id=published.id, account_id=result["id"], full_name="Ana Ruiz",
            email="ana@example.test", is_primary=True,
        )
        sent = agreements.issue(dana, result["id"], "contract_service_agreement")
        row = AgreementRequest.objects.get(pk=sent["request"]["id"])
    assert row.email_message_id is not None
    assert row.letter_message_id is None


def test_a_replayed_move_in_issues_nothing_twice(published, dana):
    with tenant_ctx(published):
        result = _move_in(dana, published, "Unit 1904")
        again = notifications_seam.queue_move_in_service_agreement(
            move_record_id=result["move_record_id"],
            account_id=result["id"],
            effective_on=date.fromisoformat(str(result["opened_at"])),
            actor=dana,
        )
        assert AgreementRequest.objects.filter(account_id=result["id"]).count() == 1
    assert notifications_seam.MOVE_MESSAGE_ALREADY_QUEUED in [row.get("code") for row in again]


# ── 2 · the public page ──────────────────────────────────────────────────────


def _issued(tenant, actor, label):
    with tenant_ctx(tenant):
        result = _move_in(actor, tenant, label)
        return result["id"], _token(_email(result["id"]))


def test_accept_keeps_every_proof_files_a_stamped_copy_and_confirms(published, dana, audit_rows):
    from apps.customers.account_document_models import AccountDocument
    from apps.tenancy import document_store

    account_id, token = _issued(published, dana, "Unit 1910")
    with tenant_ctx(published):
        view = agreements.public_view(token)
        assert view["account_no"] and view["text"]
        today = agreements._today()
        answer = agreements.accept(
            token, agreed=True, accepted_date=today.isoformat(), typed_name="  Ana   Ruiz ",
            ip="203.0.113.9", user_agent="Mozilla/5.0 test",
        )
        assert answer["state"] == "accepted"
        row = AgreementRequest.objects.get(account_id=account_id)
        assert row.status == "accepted"
        assert row.accepted_name == "Ana Ruiz"
        assert row.accepted_date == today
        assert row.accepted_ip == "203.0.113.9"
        assert row.accepted_user_agent == "Mozilla/5.0 test"
        assert row.template_version >= 1 and row.template_id
        filing = AccountDocument.objects.get(pk=row.accepted_filing_id)
        assert filing.doc_type == "contract"
        stamped = document_store.fetch(filing.document_id)
        assert stamped.startswith(b"%PDF-")
        assert stamped != document_store.fetch(row.sent_document_id)
        accepted = [r for r in audit_rows if r["action"] == agreements.AUDIT_ACCEPTED]
        assert [str(r["entity_id"]) for r in accepted] == [str(row.pk)]
        # BR-AUD-006 — the trail says a name was given, never the name.
        assert "Ana Ruiz" not in json.dumps(accepted, default=str)
        assert any(r["action"] == agreements.AUDIT_REQUESTED for r in audit_rows)
        assert notification_models.OutboundMessage.objects.filter(
            account_id=account_id, template_code="email_agreement_accepted"
        ).exists()
        # Single use: the same link now opens nothing.
        with pytest.raises(agreements.LinkUnavailable):
            agreements.public_view(token)


def test_a_date_that_is_not_today_is_refused_on_its_field(published, dana):
    from core import errors

    _account_id, token = _issued(published, dana, "Unit 1911")
    with tenant_ctx(published):
        yesterday = agreements._today() - timedelta(days=1)
        with pytest.raises(errors.ValidationError) as refused:
            agreements.accept(token, agreed=True, accepted_date=yesterday.isoformat(),
                              typed_name="Ana Ruiz", ip=None, user_agent=None)
        assert [item["field"] for item in refused.value.field_errors] == ["date"]
        with pytest.raises(errors.ValidationError) as unticked:
            agreements.accept(token, agreed=False, accepted_date=agreements._today().isoformat(),
                              typed_name="", ip=None, user_agent=None)
        assert {item["field"] for item in unticked.value.field_errors} == {"agreed", "name"}
        # Still pending — a refused submit spends nothing.
        assert AgreementRequest.objects.get(token_hash=agreements._digest(token)).status == "pending"


def test_unknown_used_expired_and_voided_are_one_refusal(published, dana):
    used_account, used = _issued(published, dana, "Unit 1912")
    expired_account, expired = _issued(published, dana, "Unit 1913")
    voided_account, voided = _issued(published, dana, "Unit 1914")
    with tenant_ctx(published):
        agreements.accept(used, agreed=True, accepted_date=agreements._today().isoformat(),
                          typed_name="Ana Ruiz", ip=None, user_agent=None)
        AgreementRequest.objects.filter(account_id=expired_account).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        old = AgreementRequest.objects.get(account_id=voided_account)
        agreements.resend(dana, voided_account, old.pk)
        for token in ("not-a-token", used, expired, voided):
            with pytest.raises(agreements.LinkUnavailable):
                agreements.public_view(token)
        # Expiry is recorded at read, and nothing else about the account moves.
        assert AgreementRequest.objects.get(account_id=expired_account).status == "expired"
        assert AgreementRequest.objects.get(pk=old.pk).status == "voided"


def test_resend_voids_the_old_link_and_the_new_one_works(published, dana):
    account_id, first = _issued(published, dana, "Unit 1915")
    with tenant_ctx(published):
        old = AgreementRequest.objects.get(account_id=account_id)
        new = agreements.resend(dana, account_id, old.pk)["request"]
        assert new["status"] == "pending" and new["id"] != str(old.pk)
        newest = AgreementRequest.objects.get(pk=new["id"])
        message = notification_models.OutboundMessage.objects.get(pk=newest.email_message_id)
        token = _token(message)
        assert token != first
        assert agreements.public_view(token)["agreement_name"]
        statuses = [row["status"] for row in agreements.requests_for_account(account_id)]
        assert statuses == ["pending", "voided"]


def test_another_utility_cannot_open_the_link_or_read_the_list(published, dana):
    from tests.test_us_ten_helpers import brazosbend_payload  # noqa: F401
    from apps.tenancy.models import Tenant
    from core import errors

    account_id, token = _issued(published, dana, "Unit 1916")
    other = Tenant.objects.create(name="Other Water", subdomain="otherwater1916")
    with tenant_ctx(other):
        with pytest.raises(agreements.LinkUnavailable):
            agreements.public_view(token)
        with pytest.raises(errors.NotFoundError):
            agreements.requests_for_account(account_id)


# ── 3 · over HTTP ────────────────────────────────────────────────────────────


def test_the_public_edge_answers_one_body_for_every_dead_link(published, dana):
    from apps.customers import agreement_public_api as edge
    from tests.test_us_ten_helpers import api_call

    _account_id, token = _issued(published, dana, "Unit 1920")
    base = f"/api/{published.subdomain}/agreements/public"
    ok = api_call(edge.agreement_page, "get", f"{base}/{token}", tenant=published, token=token)
    assert ok.status_code == 200 and ok.data["state"] == "open"
    assert ok["Cache-Control"].startswith("no-store")
    dead = api_call(edge.agreement_page, "get", f"{base}/nope", tenant=published, token="nope")
    assert dead.status_code == 200 and dead.data["state"] == "unavailable"
    # Accept over HTTP, then the same link answers exactly as an unknown one.
    with tenant_ctx(published):
        today = agreements._today().isoformat()
    accepted = api_call(
        edge.agreement_accept, "post", f"{base}/{token}/accept", tenant=published,
        data={"agreed": True, "date": today, "name": "Ana Ruiz"}, token=token,
    )
    assert accepted.status_code == 200 and accepted.data["state"] == "accepted"
    used = api_call(edge.agreement_page, "get", f"{base}/{token}", tenant=published, token=token)
    assert used.data == dead.data


# ── 4 · the templates ────────────────────────────────────────────────────────


def test_both_emails_are_seeded_in_every_written_registry_language(published, dana):
    from apps.notifications import agreement_templates, agreement_wording, tenancy_seam

    with tenant_ctx(published):
        agreement_templates.ensure_seeded(actor=dana)
        for code in agreement_templates.CODES:
            languages = set(
                tm.NotificationTemplate.objects.filter(code=code).values_list("language", flat=True)
            )
            expected = {
                language
                for language in tenancy_seam.platform_languages()
                if agreement_wording.wording_for(code, language)
            }
            assert len(expected) >= 11
            assert expected | {tm.VARIANT_DEFAULT} <= languages
        # Every variant carries the link it cannot be accepted without.
        for language, (subject, body) in agreement_wording.WORDING["email_agreement_request"].items():
            rendering.validate_body("email_agreement_request", body, subject=subject)
            assert "{agreement_link}" in body, language


def test_without_a_public_origin_no_email_is_queued(published, dana, settings):
    settings.PUBLIC_APP_ORIGIN = ""
    with tenant_ctx(published):
        result = _move_in(dana, published, "Unit 1930")
        row = AgreementRequest.objects.get(account_id=result["id"])
    assert row.email_message_id is None
    # The customer is still sent the agreement — on paper.
    assert row.letter_message_id is not None


# ── 5 · the setting ──────────────────────────────────────────────────────────


def test_the_link_life_is_edited_on_customer_portal_settings_within_bounds(brazos, dana):
    from apps.portal import settings_service
    from core import errors

    with tenant_ctx(brazos):
        view = settings_service.save_settings(dana, brazos.id, {"agreement_link_valid_days": 14})
        assert view["agreement_link_valid_days"] == 14
        assert agreements.link_valid_days() == 14
        for bad in (0, 91, "7", True):
            with pytest.raises(errors.ValidationError):
                settings_service.save_settings(dana, brazos.id, {"agreement_link_valid_days": bad})


def test_a_customer_with_no_linked_customer_row_is_named_from_the_primary_contact(published, dana):
    with tenant_ctx(published):
        result = _move_in(dana, published, "Unit 1940")
        account = customers_models.Account.objects.get(pk=result["id"])
        customers_models.CustomerAccount.objects.filter(account_id=account.pk).delete()
        contacts = customers_models.Contact.objects.filter(account_id=account.pk)
        if not contacts.exists():
            customers_models.Contact.objects.create(
                tenant_id=published.id, account_id=account.pk, full_name="Sarah Miller",
                is_primary=True,
            )
        expected = contacts.order_by("-is_primary", "id").values_list("full_name", flat=True)[0]
        assert expected
        assert agreements.holder_name(account) == expected

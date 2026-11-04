"""CR-199-BRC10 · lane TPL-SRV-EMAIL — rich email wording (S4), link
placeholders (S7) and T2: nothing unsafe reaches an email.

Read `test_t2__nothing_a_clerk_or_a_customer_types_becomes_live_html` first —
it is the safety case and every other case leans on it.

The worked figure (image 02): Pat Rivera, account AC-004211, the utility's
quick-pay page at `https://app.example.test/brazosbend/portal/pay`. A rich
"Bill ready" sends a **Pay now** button pointing there and a plain-text part
reading `Pay now: https://app.example.test/brazosbend/portal/pay`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.integrations.adapters import email_format
from apps.notifications import catalogs, dispatcher, rendering, rich_text
from apps.notifications import template_models as tm
from apps.notifications import template_service, templates_api

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

CODE = "email_bill_ready"
ORIGIN = "https://app.example.test"

RICH_BODY = (
    "Hello {first_name},\n"
    "\n"
    "Your bill for account **{account_no}** is ready.\n"
    "\n"
    "- Amount due: **{total_due}**\n"
    "- Due date: {due_date}\n"
    "\n"
    "[[Pay now|{pay_link}]]\n"
    "\n"
    "[Visit your account]({portal_link})\n"
    "\n"
    "Questions? Call {support_phone}."
)

CONTEXT = {
    "first_name": "Pat",
    "account_no": "AC-004211",
    "total_due": Decimal("84.20"),
}


@pytest.fixture()
def public_origin(settings):
    settings.PUBLIC_APP_ORIGIN = ORIGIN
    return ORIGIN


def _render(tenant, body, *, body_format="rich", context=None, lenient=False):
    with tenant_ctx(tenant):
        return rendering.render(
            template_code=CODE,
            template_version=1,
            body=body,
            context=dict(CONTEXT if context is None else context),
            subject="Your {utility_name} bill is ready",
            body_format=body_format,
            lenient=lenient,
        )


def _post(view, tenant, actor, data, **kwargs):
    return api_call(
        view,
        "post",
        user=getattr(actor, "user", None),
        role="system_admin",
        tenant=tenant,
        data=data,
        **kwargs,
    )


def _variant(tenant, actor, code=CODE):
    with tenant_ctx(tenant):
        row, _created = template_service.register(
            code=code,
            name="Bill ready",
            actor=actor,
            category=tm.VARIANT_DEFAULT,
            language=tm.VARIANT_DEFAULT,
        )
    return row


# ── T2 ─────────────────────────────────────────────────────────────────────
HOSTILE = (
    "Hi {first_name} <script>alert(1)</script>\n"
    "\n"
    '<img src=x onerror="alert(2)"> and <a href="javascript:alert(3)">click</a>\n'
    "\n"
    "[Open](javascript:alert(4)) [[Go|javascript:alert(5)]] [Plain](http://plain.example)\n"
    "\n"
    "<iframe src=//evil.example></iframe><style>body{display:none}</style>"
)


@pytest.mark.parametrize("body_format", ["rich", "plain"])
def test_t2__nothing_a_clerk_or_a_customer_types_becomes_live_html(brazos, body_format):
    """A stored body full of HTML and script links, AND a customer whose name
    is itself markup and HTML: neither reaches the email as anything live.

    The body never got past a save (see the save cases below); this is the
    render's own guarantee for a body that reached the row some other way."""
    hostile_name = '[[Click|https://evil.example]] <b onmouseover="x()">Pat</b> **bold**'
    artifact = _render(
        brazos,
        HOSTILE,
        body_format=body_format,
        context={**CONTEXT, "first_name": hostile_name},
    )
    html = artifact.html.lower()
    for needle in (
        "<script",
        "onerror",
        # A `javascript:` written as TEXT is printed as characters; what must
        # never exist is an address that runs it.
        'href="javascript',
        "<iframe",
        "<style",
        "<img src=x",
        'href="http://plain',
        "evil.example",
        'onmouseover="',
        "<b ",
    ):
        if needle == "evil.example":
            # The customer's name is PRINTED (escaped), never a link.
            assert 'href="https://evil.example' not in html
            continue
        assert needle not in html, needle
    # The customer's value arrives as their characters, escaped.
    assert "&lt;b onmouseover=" in artifact.html
    assert "[[Click|https://evil.example]]" in artifact.body
    # And the plain-text part carries no tag either.
    for needle in ("<script", "<img", "<iframe", "<style", "onerror"):
        assert needle not in artifact.body.lower(), needle


def test_t2__the_save_refuses_raw_html_and_unsafe_links_by_name(brazos, dana):
    variant = _variant(brazos, dana)
    cases = [
        ("Hi <b>{first_name}</b>", "notifications.templates.htmlNotAllowed", {}),
        (
            "Pay at [here](http://pay.example)",
            "notifications.templates.linkTargetNotAllowed",
            {"target": "http://pay.example"},
        ),
        (
            "[[Go|javascript:void]]",
            "notifications.templates.linkTargetNotAllowed",
            {"target": "javascript:void"},
        ),
        (
            # `{first_name}` is in the palette but is not an ADDRESS.
            "[[Go|{first_name}]]",
            "notifications.templates.linkTargetNotAllowed",
            {"target": "{first_name}"},
        ),
    ]
    for body, key, params in cases:
        for body_format in ("rich", "plain"):
            response = _post(
                templates_api.save_draft,
                brazos,
                dana,
                {"variant": str(variant.pk), "body": body, "body_format": body_format},
                code=CODE,
            )
            assert response.status_code == 422, (body, response.data)
            assert response.data["message_key"] == key, (body, response.data)
            for name, value in params.items():
                assert response.data["params"][name] == value
            assert [e["field"] for e in response.data["field_errors"]] == ["body"]


# ── A2 A — an unknown placeholder blocks saving, by name ─────────────────────
def test_a2a__an_unknown_placeholder_is_refused_naming_it(brazos, dana):
    variant = _variant(brazos, dana)
    response = _post(
        templates_api.save_draft,
        brazos,
        dana,
        {"variant": str(variant.pk), "body": "Hello {first_name}, {bogus}", "body_format": "rich"},
        code=CODE,
    )
    assert response.status_code == 422
    assert response.data["message_key"] == "notifications.templates.placeholderUnknown"
    assert response.data["params"]["token"] == "bogus"
    assert response.data["params"]["placeholder"] == "{bogus}"


def test_a2a__the_preview_shows_the_wording_and_names_the_unknown_one(brazos, dana, public_origin):
    """Image 17: the preview still renders, `{bogus}` as typed, with the error
    the save would refuse with, and the bare-link warning beside it."""
    response = _post(
        templates_api.preview_body,
        brazos,
        dana,
        {"body": "Hello {first_name}, pay at {pay_link} {bogus}", "body_format": "rich"},
        code=CODE,
    )
    assert response.status_code == 200, response.data
    data = response.data
    assert "{bogus}" in data["text"]
    assert {
        "code": "placeholder_unknown",
        "message_key": "notifications.templates.placeholderUnknown",
        "params": {"token": "bogus", "placeholder": "{bogus}"},
    } in data["errors"]
    assert data["warnings"] == [
        {
            "code": "link_placeholder_as_text",
            "message_key": "notifications.templates.linkAsText",
            "params": {"token": "pay_link", "placeholder": "{pay_link}"},
        }
    ]
    # Plain text prints the full address — and no warning, by design.
    plain = _post(
        templates_api.preview_body,
        brazos,
        dana,
        {"body": "Hello {first_name}, pay at {pay_link}", "body_format": "plain"},
        code=CODE,
    ).data
    assert plain["warnings"] == []
    assert f"pay at {ORIGIN}/brazosbend/portal/pay" in plain["text"]


# ── S4 — rich wording ────────────────────────────────────────────────────────
def test_s4__a_rich_body_sends_a_button_a_link_bold_and_a_list(brazos, public_origin):
    artifact = _render(brazos, RICH_BODY)
    pay = f"{ORIGIN}/brazosbend/portal/pay"
    portal = f"{ORIGIN}/brazosbend/portal"
    assert artifact.body_format == "rich"
    assert f'<a href="{pay}" style="display:inline-block;' in artifact.html
    assert ">Pay now</a>" in artifact.html
    assert f'<a href="{portal}" style="color:' in artifact.html
    assert "<strong>AC-004211</strong>" in artifact.html
    assert "<li" in artifact.html and "<ul" in artifact.html
    # The plain-text part: every link as its full address, no markup.
    assert f"Pay now: {pay}" in artifact.body
    assert f"Visit your account: {portal}" in artifact.body
    assert "**" not in artifact.body and "[[" not in artifact.body
    assert "- Amount due: " in artifact.body


def test_s4__the_same_body_in_plain_format_carries_no_formatting(brazos, public_origin):
    artifact = _render(brazos, RICH_BODY, body_format="plain")
    assert artifact.body_format == "plain"
    body_html = artifact.html.split("padding:24px;", 1)[1]
    assert "<a " not in body_html.split("</td>", 1)[0]
    assert "<strong>" not in artifact.html
    assert f"Pay now: {ORIGIN}/brazosbend/portal/pay" in artifact.body


def test_s4__a_markup_free_body_keeps_its_text_byte_for_byte(brazos):
    """Every email written before rich existed: the plain-text part is exactly
    what the old renderer produced — the same line breaks, the same blanks."""
    body = "Hi {first_name},\n\n\n  Account {account_no}\t\n- a dash line\nEnd"
    artifact = _render(brazos, body, body_format="plain")
    assert artifact.body == "Hi Pat,\n\n\n  Account AC-004211\t\n- a dash line\nEnd"


def test_s4__a_rich_save_is_stored_and_served_as_rich(brazos, dana):
    variant = _variant(brazos, dana)
    response = _post(
        templates_api.save_draft,
        brazos,
        dana,
        {"variant": str(variant.pk), "body": RICH_BODY, "body_format": "rich"},
        code=CODE,
    )
    assert response.status_code == 201, response.data
    assert response.data["body_format"] == "rich"
    with tenant_ctx(brazos):
        row = tm.NotificationTemplateVersion.objects.get(pk=response.data["id"])
        assert row.body_format == "rich"
        pinned = template_service.load_pinned(template_id=variant.pk, version=row.version)
        assert pinned.body_format == "rich"


def test_s4__rich_is_refused_off_email_and_an_unknown_format_by_name(brazos, dana):
    sms = _variant(brazos, dana, code="sms_bill_ready")
    response = _post(
        templates_api.save_draft,
        brazos,
        dana,
        {"variant": str(sms.pk), "body": "Bill ready {utility_name}", "body_format": "rich"},
        code="sms_bill_ready",
    )
    assert response.status_code == 422
    variant = _variant(brazos, dana)
    response = _post(
        templates_api.save_draft,
        brazos,
        dana,
        {"variant": str(variant.pk), "body": "Hi", "body_format": "html"},
        code=CODE,
    )
    assert response.status_code == 422  # core.errors: a validation error is 422
    assert response.data["message_key"] == "notifications.templates.bodyFormatUnknown"


def test_s4__the_detail_offers_rich_on_email_only(brazos, dana):
    detail = api_call(
        templates_api.template_detail,
        "get",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        code=CODE,
    ).data
    assert detail["body_formats"] == ["plain", "rich"]
    sms = api_call(
        templates_api.template_detail,
        "get",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        code="sms_bill_ready",
    ).data
    assert sms["body_formats"] == ["plain"]


# ── S7 — link placeholders ───────────────────────────────────────────────────
def test_s7__the_picker_tags_link_placeholders(brazos, dana, public_origin):
    detail = api_call(
        templates_api.template_detail,
        "get",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        code=CODE,
    ).data
    rows = {row["token"]: row for row in detail["merge_field_rows"]}
    for token in ("pay_link", "portal_link", "bill_link"):
        assert rows[token]["kind"] == "link", token
    assert rows["first_name"]["kind"] == "text"
    assert rows["first_name"]["label"] == "First name"
    assert rows["link_expires_on"]["kind"] == "text"
    # The two the renderer supplies show the REAL address, not a sample.
    assert rows["pay_link"]["sample_value"] == f"{ORIGIN}/brazosbend/portal/pay"
    assert rows["portal_link"]["sample_value"] == f"{ORIGIN}/brazosbend/portal"


def test_s7__customer_emails_offer_pay_and_portal_links_and_staff_emails_do_not():
    assert {"pay_link", "portal_link"} <= catalogs.catalog_for("email_past_due").tokens
    assert "pay_link" not in catalogs.catalog_for("staff_user_invite").tokens
    assert "pay_link" not in catalogs.catalog_for("sms_bill_ready").tokens
    assert catalogs.is_link_token("bill_link") and not catalogs.is_link_token("link_expires_on")


def test_s7__no_public_address_prints_the_label_alone_never_a_broken_link(brazos, settings):
    settings.PUBLIC_APP_ORIGIN = ""
    artifact = _render(brazos, "[[Pay now|{pay_link}]]")
    assert "href=" not in artifact.html.split("padding:24px;", 1)[1].split("</td>", 1)[0]
    assert artifact.body == "Pay now"


# ── S6 — the payload carries the branded HTML to every email adapter ─────────
def test_s6__the_dispatcher_payload_carries_html_and_compose_sends_it(brazos, public_origin):
    artifact = _render(brazos, RICH_BODY)

    class _Row:
        pk = "00000000-0000-0000-0000-000000000001"
        channel = "email"
        recipient_address = "pat@example.test"
        recipient_snapshot = {}
        source_type = "invoice"
        source_id = "x"
        account_id = None

    payload = dispatcher._payload(_Row(), artifact)
    assert payload["artifact"]["html"] == artifact.html
    content = email_format.compose(
        subject=artifact.subject, body=artifact.body, html=payload["artifact"]["html"]
    )
    assert content.html == artifact.html
    assert content.text == artifact.body
    # No html (a test send, an older caller): exactly as before.
    fallback = email_format.compose(subject="S", body="a\n\nb")
    assert fallback.html == email_format.html_alternative("S", "a\n\nb")


def test_the_markup_reads_the_renderers_own_token_grammar():
    assert rich_text.TOKEN_PATTERN == rendering.TOKEN_RE.pattern

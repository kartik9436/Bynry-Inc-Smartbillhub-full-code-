"""CR-199-BRC10 · lane TPL-SRV-EMAIL — the branded email layout (S6) and the
logo link set once in Settings › Company › Branding (S5, PO ruling 1A).

The worked figure (image 02): Brazos Bend's primary colour `#1B5E9E` is the
header band with white type on it; its logo links to
`https://brazosbendutilities.com`; the footer reads the utility's name and its
mailing address, and nothing of ours.
"""

from __future__ import annotations

import pytest

from apps.notifications import email_layout, rendering
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import audit_actions, tenant_ctx
from tests.test_us_ten_helpers import api_call  # noqa: F401

pytestmark = pytest.mark.django_db

LINK = "https://brazosbendutilities.com"


def _render(tenant, body="Hello {first_name}"):
    with tenant_ctx(tenant):
        return rendering.render(
            template_code="email_past_due",
            template_version=1,
            body=body,
            context={"first_name": "Pat"},
            subject="A reminder from {utility_name}",
            body_format="rich",
        )


def _save(tenant, actor, changes):
    with tenant_ctx(tenant):
        return tenancy_services.save_company_profile(actor, changes)


def _header(html: str) -> str:
    return html.split("font-size:18px;font-weight:700;", 1)[1].split("</td>", 1)[0]


# ── S5 — the logo link, https only, audited, served ──────────────────────────
def test_s5__the_logo_link_saves_https_only_is_audited_and_served(brazos, dana, audit_rows):
    for bad in (
        "http://brazosbendutilities.com",
        "javascript:alert(1)",
        "https://user:pw@brazosbendutilities.com",
        'https://x.example/"onmouseover=x',
        "brazosbendutilities.com",
        "https://" + "a" * 600 + ".example",
    ):
        with pytest.raises(Exception) as refused:
            _save(brazos, dana, {"brand_logo_link_url": bad})
        fields = {fe["field"]: fe for fe in refused.value.field_errors}
        assert fields["brand_logo_link_url"]["message_key"] == "settings.company.logoLinkHttps", bad

    _save(brazos, dana, {"brand_logo_link_url": LINK})
    with tenant_ctx(brazos):
        assert tenancy_selectors.company_profile()["brand_logo_link_url"] == LINK
    saved = [row for row in audit_rows if row["action"] == "settings.company_profile.updated"]
    assert saved and saved[-1]["after"]["brand_logo_link_url"] == LINK
    assert "settings.company_profile.updated" in audit_actions(audit_rows)
    # Cleared → null, and the logo links nowhere.
    _save(brazos, dana, {"brand_logo_link_url": ""})
    with tenant_ctx(brazos):
        assert tenancy_selectors.company_profile()["brand_logo_link_url"] is None


# ── S6 — the frame ───────────────────────────────────────────────────────────
def test_s6__the_band_is_the_brand_colour_and_the_logo_links_to_the_utility(brazos, dana, settings):
    settings.PUBLIC_API_BASE_URL = "https://api.example.test"
    _save(
        brazos,
        dana,
        {"brand_primary_hex": "#1B5E9E", "brand_logo_link_url": LINK},
    )
    artifact = _render(brazos)
    header = _header(artifact.html)
    assert "background-color:#1B5E9E;color:#FFFFFF" in artifact.html
    assert f'<a href="{LINK}"' in header
    # No logo uploaded → the band carries the name alone, never a broken <img>.
    assert "<img" not in header
    assert artifact.branding["logo_link_url"] == LINK
    assert artifact.branding["band_hex"] == "#1B5E9E"


def test_s6__with_no_logo_link_the_header_is_not_a_link(brazos, dana):
    _save(brazos, dana, {"brand_logo_link_url": ""})
    header = _header(_render(brazos).html)
    assert "<a " not in header
    assert "Brazos Bend" in header


def test_s6__a_logo_on_file_is_drawn_from_the_public_api_host(brazos, settings, monkeypatch):
    settings.PUBLIC_API_BASE_URL = "https://api.example.test"
    real = tenancy_selectors.company_profile

    def with_logo():
        return {**real(), "has_logo": True, "logo_ref": "doc-123"}

    monkeypatch.setattr(tenancy_selectors, "company_profile", with_logo)
    header = _header(_render(brazos).html)
    assert (
        '<img src="https://api.example.test/api/brazosbend/settings/company/logo/file?v=doc-123"'
        in header
    )
    # No public API host on this server → no image, never a relative one.
    settings.PUBLIC_API_BASE_URL = ""
    assert "<img" not in _header(_render(brazos).html)


def test_s6__the_footer_is_facts_only_and_escaped(brazos, dana):
    _save(brazos, dana, {"mailing_address": "9410 FM 1093 Rd <b>Katy</b>, TX 77494"})
    html = _render(brazos).html
    footer = html.rsplit("font-size:12px;", 1)[1]
    assert "9410 FM 1093 Rd &lt;b&gt;Katy&lt;/b&gt;, TX 77494" in footer
    assert "<b>" not in footer
    # No prose of ours: no "Email preferences", no "You receive this because".
    assert "preferences" not in html.lower()
    assert "you receive this" not in html.lower()


def test_s6__the_document_declares_its_language_and_loads_no_stylesheet(brazos):
    html = _render(brazos).html
    assert html.startswith("<!DOCTYPE html><html")
    assert "<link" not in html and "<style" not in html and "<script" not in html


def test_s6__ink_follows_contrast_and_a_bad_colour_falls_back():
    assert email_layout.band_colours("#1B5E9E") == ("#1B5E9E", "#FFFFFF")
    assert email_layout.band_colours("#F5F5F5") == ("#F5F5F5", email_layout.DARK_INK)
    assert email_layout.band_colours("red; x:y") == (email_layout.FALLBACK_BAND_HEX, "#FFFFFF")
    assert email_layout.band_colours(None)[0] == email_layout.FALLBACK_BAND_HEX


def test_s6__a_logo_link_that_reached_the_row_unsafely_is_never_an_href():
    brand = email_layout.branding({"brand_logo_link_url": "javascript:alert(1)"}, None)
    assert brand["logo_link_url"] is None
    html = email_layout.wrap(
        subject="S",
        body_html="",
        identity={"dba_name": "X", "brand_logo_link_url": "javascript:alert(1)"},
        logo_url=None,
        language="es-MX",
    )
    assert "javascript" not in html
    assert '<html lang="es-MX">' in html


def test_s6__preview_returns_text_and_html(brazos, dana):
    from tests.test_us_ten_helpers import api_call as call

    from apps.notifications import templates_api

    response = call(
        templates_api.preview_body,
        "post",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={"body": "Hello {first_name}\n\n[[Pay now|{pay_link}]]", "body_format": "rich"},
        code="email_past_due",
    )
    assert response.status_code == 200, response.data
    data = response.data
    assert data["html"].startswith("<!DOCTYPE html>")
    assert data["text"].startswith("Hello Pat")
    assert data["body_format"] == "rich"
    assert set(data["branding"]) >= {"band_hex", "ink_hex", "logo_url", "logo_link_url"}
    assert data["plain_source"] == "Hello {first_name}\n\nPay now: {pay_link}"

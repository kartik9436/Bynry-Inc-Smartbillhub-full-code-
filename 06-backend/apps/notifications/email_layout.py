# ── Trace ──────────────────────────────────────────────
# Change:   CR-199-BRC10 · lane TPL-SRV-EMAIL · task S6 (the branded email
#           layout) · S5 (the logo links to the utility's own address)
# Rulings:  PO 2026-10-29 — 1A (the logo link is set ONCE per utility in
#           Settings › Company › Branding) · 2A (a safe preview)
# Rules:    BR-TEN-017 (the utility's identity is read AT RENDER) ·
#           BR-NOT-012 (every value escaped) · B14 rule 33 (no prose of ours
#           on a customer's email: the footer carries FACTS only)
# Tests:    06-backend/tests/test_cr199_email_layout.py
# ───────────────────────────────────────────────────────
"""Every customer email, inside the utility's own frame (image 02).

    ┌──────────────────────────────────────────┐
    │ ▆ [logo] Utility name      ← brand band   │  logo → brand_logo_link_url
    ├──────────────────────────────────────────┤
    │ the body (rich_text)                      │
    ├──────────────────────────────────────────┤
    │ Utility name · mailing address  ← footer  │
    └──────────────────────────────────────────┘

**The frame carries no words of ours.** The band is the utility's name; the
footer is its name and mailing address from Settings › Company. The drawing's
*"You receive this because you have an account with us. Email preferences"* is
NOT built: no email-preferences page exists today (the CR says *"where one
exists today"*), and a sentence of ours in English would be wrong on every
Spanish email. Every rights footer a body carries (`{rights_footer}`) is in the
body and is untouched.

**Loads nothing but the logo.** Inline styles only, no stylesheet, no font, no
tracking pixel. The logo comes from the utility's one public logo address on
the API host (`tenancy_seam.logo_image_url`); with no `PUBLIC_API_BASE_URL` or
no logo the band shows the name alone — never a broken image.

**The link is the utility's, and only if it is safe.** `brand_logo_link_url`
is validated `https://` on save (`tenancy.services.brand_logo_link_ok`) and
checked again here, so a value that reached the row by any other path still
cannot become an `href`. Unset → the logo is not a link.
"""

from __future__ import annotations

import html as _html
import re
from typing import Any

from apps.notifications import rich_text

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")

#: Used only when the utility has set no primary colour: the product's own ink.
FALLBACK_BAND_HEX = "#1F2933"
DARK_INK = "#1F2933"
LIGHT_INK = "#FFFFFF"


def _luminance(hex_value: str) -> float:
    channels = [int(hex_value[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def band_colours(primary_hex: object) -> tuple[str, str]:
    """(band, ink): the utility's primary colour and whichever of white or the
    dark ink reads better on it (WCAG contrast). A missing or malformed colour
    falls back to the product's ink rather than to a guess."""
    band = (
        primary_hex
        if isinstance(primary_hex, str) and _HEX.match(primary_hex)
        else FALLBACK_BAND_HEX
    )
    ink = LIGHT_INK if _contrast(band, LIGHT_INK) >= _contrast(band, DARK_INK) else DARK_INK
    return band.upper(), ink


def utility_name(identity: dict[str, Any]) -> str | None:
    return identity.get("dba_name") or identity.get("legal_name") or None


def branding(identity: dict[str, Any], logo_url: str | None) -> dict[str, Any]:
    """What the preview's branding line says (image 02: *"Springfield blue ·
    Logo links to springfieldwater.gov"*) — facts, for the screen to word."""
    link = identity.get("brand_logo_link_url")
    band, ink = band_colours(identity.get("brand_primary_hex"))
    return {
        "brand_primary_hex": identity.get("brand_primary_hex"),
        "band_hex": band,
        "ink_hex": ink,
        "has_logo": bool(identity.get("has_logo")),
        "logo_url": logo_url,
        "logo_link_url": link if rich_text.safe_https(link) else None,
        "utility_name": utility_name(identity),
    }


def wrap(
    *,
    subject: str,
    body_html: str,
    identity: dict[str, Any],
    logo_url: str | None,
    language: str | None,
) -> str:
    """The whole HTML document: `<html lang>`, the band, the body, the footer."""
    brand = branding(identity, logo_url)
    band, ink = brand["band_hex"], brand["ink_hex"]
    name = brand["utility_name"]
    esc = lambda value: _html.escape(str(value), quote=True)  # noqa: E731

    mark = ""
    if logo_url:
        mark = (
            f'<img src="{esc(logo_url)}" alt="{esc(name or "")}" height="32" '
            'style="display:inline-block;height:32px;max-width:160px;border:0;'
            'vertical-align:middle;margin-right:12px;"/>'
        )
    title = f'<span style="vertical-align:middle;">{esc(name)}</span>' if name else ""
    header = mark + title
    if header and brand["logo_link_url"]:
        header = (
            f'<a href="{esc(brand["logo_link_url"])}" '
            f'style="color:{ink};text-decoration:none;">{header}</a>'
        )

    footer_parts = [part for part in (name, identity.get("mailing_address")) if part]
    footer = " · ".join(esc(" ".join(str(part).split())) for part in footer_parts)

    lang = ""
    if isinstance(language, str):
        tag = language.strip().replace("_", "-")
        if tag and tag != "default" and _LANGUAGE_TAG.match(tag):
            lang = f' lang="{esc(tag)}"'

    return (
        "<!DOCTYPE html>"
        f'<html{lang}><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(subject)}</title></head>"
        '<body style="margin:0;padding:0;background-color:#F3F2F2;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background-color:#F3F2F2;"><tr><td align="center" style="padding:16px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:600px;background-color:#FFFFFF;border-collapse:collapse;">'
        f'<tr><td style="background-color:{band};color:{ink};padding:16px 24px;'
        'font-family:Arial,Helvetica,sans-serif;font-size:18px;font-weight:700;">'
        f"{header}</td></tr>"
        '<tr><td style="padding:24px;font-family:Arial,Helvetica,sans-serif;font-size:16px;'
        f'line-height:1.5;color:#1F2933;word-wrap:break-word;">{body_html}</td></tr>'
        + (
            '<tr><td style="padding:16px 24px;border-top:1px solid #E4E2E2;'
            "font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.5;"
            f'color:#5F6B76;">{footer}</td></tr>'
            if footer
            else ""
        )
        + "</table></td></tr></table></body></html>"
    )

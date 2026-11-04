# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-005 (S8 Company profile → Brand)  Screens: S8, shell-chrome
# Change:   CR-048 wave D — the utility's own mark.
# Defect:   DEF-195 (the mark was ruled 2026-08-16 and drawn nowhere) ·
#           DEF-192 (no route streams the logo bytes, so no document can draw
#           a logo even where one exists — hard-won law 2).
# Rules:    BR-TEN-019 (logo allowlist/cap/sanitizer; brand colours #RRGGBB) ·
#           BR-TEN-088 (the generated two-letter mark — CR-007 PO ruling
#           2026-08-16, *"Create name based or initial base dummy logo"* and
#           *"2 letters"*) · CLAUDE.md hard rule 1 (tenant scoping).
# Tests:    this file. The isolation half carries @pytest.mark.isolation and
#           needs live Postgres (tests/isolation_helpers.py).
# ───────────────────────────────────────────────────────
"""CR-048 wave D — the two-letter mark, the readable ink, and the logo read.

Three things are proved here and they fail three different ways without the
lane's code:

  1. `apps.tenancy.brand` does not exist            → ImportError (D2)
  2. `GET /settings/company/logo` is not routed     → 405 (D1)
  3. `company_profile()` publishes no `mark`        → KeyError (D2/D3)

The contrast case is the one worth reading twice. The product does not tell a
utility its brand colours are wrong; it keeps their colour and chooses the INK
(black or white) that is readable on it — see `apps/tenancy/brand.py` for the
threshold and its derivation.
"""

import pytest

from apps.tenancy import api, models, selectors, services
from tests.isolation_helpers import live_tenant_context, requires_postgres
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    FakeUser,
    api_call,
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
OTHER_PNG = PNG_1PX[:-4] + b"\x00\x00\x00\x00" + b"\x89PNG"  # different bytes, same shape


def _read_logo(tenant, *, role="system_admin", headers=None):
    return api_call(
        api.company_logo_file,
        "get",
        user=FakeUser(),
        role=role,
        tenant=tenant,
        headers=headers,
    )


def _store_logo(tenant, content=PNG_1PX, name="mark.png"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return api_call(
        api.company_logo,
        "post",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        data={"file": SimpleUploadedFile(name, content, content_type="image/png")},
        body_format="multipart",
    )


# ══ D2 · the letters ═══════════════════════════════════════════════════════
@pytest.mark.parametrize(
    ("dba", "legal", "expected"),
    [
        # The PO's own example. Both names begin "Silver Creek", so the rule
        # that picks between them does not show here — which is why the row
        # below it exists.
        ("Silver Creek Water", "Silver Creek Water & Sanitation District", "SC"),
        # Trading name WINS, and it is not a prefix of the legal name.
        ("Brazos Bend Utilities", "Brazos Bend Utility District No. 1", "BB"),
        ("Hilltop Power", "Ridgeline Holdings LLC", "HP"),
        # No trading name → the legal name. First letter of the first TWO
        # words, so "Lone Star …" is LS — not the initials a human would pick
        # out of the whole phrase, which is a rule nobody could predict.
        ("", "Lone Star Ridge Water Co-op", "LS"),
        (None, "Lone Star Ridge Water Co-op", "LS"),
        # One word → its first TWO letters, never one letter and a blank.
        ("Aquaflow", "Aquaflow Inc", "AQ"),
        # Punctuation-only tokens are not letters: "&" never becomes a letter.
        ("Water & Power", "Water and Power Co", "WP"),
        # A single character is all there is — one letter, honestly.
        ("Q", "Q", "Q"),
        # Digits are characters a name can start with (3M, 1st Utility).
        ("1st Utility District", "1st Utility District", "1U"),
        # Lowercase input, uppercase mark.
        ("silver creek water", "silver creek water", "SC"),
    ],
)
def test_cr048_mark_letters__two_from_the_trading_name_then_the_legal_name(dba, legal, expected):
    from apps.tenancy import brand

    assert brand.mark_letters(dba, legal) == expected


def test_cr048_mark_letters__neither_name_falls_back_to_the_registered_name():
    """A tenant has `name` from the signup form before it has either profile
    name, so the mark is never blank on day one."""
    from apps.tenancy import brand

    assert brand.mark_letters(None, None, fallback="Brazos Bend Utilities") == "BB"
    assert brand.mark_letters("", "", fallback="") == ""


# ══ D2 · the ink, and the judgment call behind it ══════════════════════════
def test_cr048_ink__dark_brand_gets_white_letters_and_pale_brand_gets_black():
    from apps.tenancy import brand

    assert brand.readable_ink("#1B5E9E") == brand.INK_LIGHT  # a navy → white letters
    assert brand.readable_ink("#F5E9A0") == brand.INK_DARK  # OQ-800's pale yellow → black
    assert brand.readable_ink("#000000") == brand.INK_LIGHT
    assert brand.readable_ink("#FFFFFF") == brand.INK_DARK


def test_cr048_ink__every_colour_a_tenant_can_pick_clears_wcag_aa():
    """THE reason this rule is safe to apply without asking the tenant.

    Choosing the higher-contrast ink of black/white guarantees a floor of
    4.58:1 over the WHOLE RGB cube — above WCAG AA's 4.5:1 for normal text. So
    the product never has to tell a utility their colours are wrong.
    """
    from apps.tenancy import brand

    worst = 21.0
    worst_hex = None
    for r in range(0, 256, 15):
        for g in range(0, 256, 15):
            for b in range(0, 256, 15):
                background = f"#{r:02X}{g:02X}{b:02X}"
                ratio = brand.contrast_ratio(brand.readable_ink(background), background)
                if ratio < worst:
                    worst, worst_hex = ratio, background
    assert worst >= brand.WCAG_AA_NORMAL_TEXT, f"{worst_hex} only reaches {worst:.2f}:1"
    # And the floor is the crossover, not luck: 4.58:1, at the threshold hue.
    assert worst == pytest.approx(4.58, abs=0.02)


def test_cr048_ink__the_threshold_is_the_crossover_and_not_a_taste():
    """`INK_LUMINANCE_THRESHOLD` is the L where white and black tie. Above it
    black wins, below it white does — so the constant is derivable, and a
    future PO overrule moves ONE number."""
    from apps.tenancy import brand

    assert brand.INK_LUMINANCE_THRESHOLD == pytest.approx(0.179, abs=0.001)
    just_below = brand.hex_for_luminance(brand.INK_LUMINANCE_THRESHOLD - 0.02)
    just_above = brand.hex_for_luminance(brand.INK_LUMINANCE_THRESHOLD + 0.02)
    assert brand.readable_ink(just_below) == brand.INK_LIGHT
    assert brand.readable_ink(just_above) == brand.INK_DARK


def test_cr048_ink__a_malformed_or_absent_colour_is_not_guessed_at():
    from apps.tenancy import brand

    assert brand.readable_ink(None) is None
    assert brand.readable_ink("") is None
    assert brand.readable_ink("teal") is None
    assert brand.readable_ink("#12345") is None
    # Three-digit CSS hex is a real form a tenant can type into the field.
    assert brand.readable_ink("#111") == brand.INK_LIGHT


# ══ D2/D3 · the mark on the company profile ════════════════════════════════
def test_cr048_profile__publishes_the_mark_beside_the_logo(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_company_profile(
            admin_actor(),  # noqa: F405
            {
                "legal_name": "Brazos Bend Utility District No. 1",
                "dba_name": "Brazos Bend Utilities",
                "brand_primary_hex": "#1B5E9E",
            },
        )
        profile = selectors.company_profile()
    mark = profile["mark"]
    assert mark["letters"] == "BB"
    assert mark["background_hex"] == "#1B5E9E"
    assert mark["ink_hex"] == "#FFFFFF"
    assert mark["contrast_ratio"] >= 4.5
    # The mark is published ALWAYS; `has_logo` is what a renderer branches on,
    # so a caller never has to reason about which of two fields is authoritative.
    assert profile["has_logo"] is False


def test_cr048_profile__mark_without_a_brand_colour_states_the_absence(growth_plan, identity_seam):
    """No colour is not a licence to invent one. The mark carries its letters
    and nulls; the caller falls back to a token it already owns.

    Provisioning seeds `#1B5E9E` (services.provision_tenant), so this is the
    tenant that CLEARED it — and a tenant provisioned before that seed landed.
    """
    tenant, _ = provisioned_tenant()
    models.Tenant.objects.filter(pk=tenant.pk).update(brand_primary_hex=None)
    with tenant_ctx(tenant):
        profile = selectors.company_profile()
    assert profile["mark"]["letters"] == "BB"  # from `tenants.name`
    assert profile["mark"]["background_hex"] is None
    assert profile["mark"]["ink_hex"] is None
    assert profile["mark"]["contrast_ratio"] is None


def test_cr048_profile__has_logo_flips_when_one_is_uploaded(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    assert _store_logo(tenant).status_code == 201
    with tenant_ctx(tenant):
        profile = selectors.company_profile()
    assert profile["has_logo"] is True
    assert profile["mark"]["letters"] == "BB"  # still generated — the fallback never goes away


# ══ D1 · the bytes come back out ═══════════════════════════════════════════
def test_cr048_logo_read__serves_the_stored_bytes_with_their_type(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    _store_logo(tenant)
    response = _read_logo(tenant)
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response.content == PNG_1PX
    # A logo is tenant data, never a shared cache entry.
    assert "private" in response["Cache-Control"]
    assert response["Content-Disposition"].startswith("inline")


def test_cr048_logo_read__no_logo_is_a_404_not_an_empty_200(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    response = _read_logo(tenant)
    assert response.status_code == 404


def test_cr048_logo_read__is_conditional_on_the_content_hash(growth_plan, identity_seam):
    """The reference is a strong ETag — the app header re-renders on every
    navigation and should not re-download.

    ⚠ AMENDED 2026-10-05 (`CR-172-BRC10`): the reference is now the logo's
    STORED DOCUMENT id in the common store, not `sha256:<hex>` of bytes on the
    row. It is still strong — a stored document is write-once, so one id is
    one set of bytes — and a replacement is a new id."""
    tenant, _ = provisioned_tenant()
    _store_logo(tenant)
    first = _read_logo(tenant)
    etag = first["ETag"]
    tenant.refresh_from_db()
    assert etag == f'"{tenant.logo_file_id}"'
    again = _read_logo(tenant, headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.content == b""


def test_cr048_logo_read__every_signed_in_role_may_read_it(growth_plan, identity_seam):
    """The app header draws it for whoever is looking. Writing stays System
    Admin (BR-TEN-019 + the CR-005/006/007 Settings ruling) — proved next."""
    tenant, _ = provisioned_tenant()
    _store_logo(tenant)
    for role in ("system_admin", "billing_clerk", "executive"):
        assert _read_logo(tenant, role=role).status_code == 200


def test_cr048_logo_read__adds_no_second_write_path(growth_plan, identity_seam):
    """The read route answers GET and nothing else — an upload has ONE door."""
    tenant, _ = provisioned_tenant()
    for method in ("post", "put", "delete"):
        response = api_call(
            api.company_logo_file,
            method,
            user=FakeUser(),
            role="system_admin",
            tenant=tenant,
        )
        assert response.status_code == 405, method


def test_cr048_logo_read__refuses_without_a_tenant_context(growth_plan, identity_seam):
    """Hard rule 1: no tenant table is touched without one. `require_tenant`
    answers AUTH-003 through the BE-02 envelope — a wiring fault, said loudly,
    rather than a row from whichever tenant happened to be first."""
    provisioned_tenant()
    response = api_call(api.company_logo_file, "get", user=FakeUser(), role="system_admin")
    assert response.status_code in (401, 404)


# ══ D1 · isolation (CLAUDE.md hard rule 1) ═════════════════════════════════
def test_cr048_logo_read__one_utility_never_receives_anothers_bytes(growth_plan, identity_seam):
    """App-layer scoping, on any vendor. `tenants` is RLS-EXEMPT by B2 §3
    (isolation_helpers.RLS_EXEMPT_TABLES), so the app layer IS the guarantee
    for this table and it is proved here rather than assumed."""
    brazos, _ = provisioned_tenant(brazosbend_payload())
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    _store_logo(brazos, PNG_1PX)
    _store_logo(lonestar, OTHER_PNG)

    assert _read_logo(brazos).content == PNG_1PX
    assert _read_logo(lonestar).content == OTHER_PNG
    assert _read_logo(brazos).content != _read_logo(lonestar).content

    # And the selector under one context can reach no other row at all.
    with tenant_ctx(brazos):
        assert bytes(selectors.logo_bytes()[0]) == PNG_1PX
    with tenant_ctx(lonestar):
        assert bytes(selectors.logo_bytes()[0]) == OTHER_PNG


@pytest.mark.isolation
@requires_postgres
def test_cr048_logo_read__isolated_on_live_postgres(growth_plan, identity_seam):
    """The same proof with the REAL `app.tenant_id` GUC set by the shipping
    kernel — so a wrong filter cannot hide behind a sqlite fixture."""
    brazos, _ = provisioned_tenant(brazosbend_payload())
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    _store_logo(brazos, PNG_1PX)
    _store_logo(lonestar, OTHER_PNG)

    with live_tenant_context(brazos.id):
        content, content_type, reference = selectors.logo_bytes()
        assert bytes(content) == PNG_1PX
        assert content_type == "image/png"

    with live_tenant_context(lonestar.id):
        assert bytes(selectors.logo_bytes()[0]) == OTHER_PNG

    # Nothing in the read path accepts a tenant id from the caller: the ONLY
    # input is the GUC, so there is no argument a caller could pass to reach
    # the other row.
    with live_tenant_context(brazos.id):
        assert selectors.logo_bytes()[2] == reference
        assert bytes(selectors.logo_bytes()[0]) != OTHER_PNG


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-048 wave D (12-governance/11-change-requests.md) · CR-007 PO ruling 2026-08-16 · OQ-257 · OQ-800
# generated: 2026-08-30 by the CR-048 wave-D lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-005 (S8 Company profile tab) · US-TEN-006 (S8 Regional,
#           formats & fiscal calendar tab)
# Rules:    BR-TEN-016/017/018/019/024 (company) · BR-TEN-020/021/022/042 +
#           BR-TEN-043 (regional/fiscal; currency lock)
# Journeys: J5 step 3 context (fiscal close derivation feeds ledger W5)
# Note:     E2-candidates implemented per the BR register (STATUS AUTHORITY),
#           reported not resolved: TC-4's warn-and-confirm predates the
#           BR-TEN-042 hard lock; TC-6's "en only" predates the LC-2 language
#           set. Document re-render halves (TC-2/3) are issuing-module scope.
# ───────────────────────────────────────────────────────
"""US-TEN-005 / US-TEN-006 — Company + Regional/fiscal settings services."""

from datetime import date

import pytest

import apps.billing.services as billing_services
from apps.tenancy import api, models, selectors, services
from core import errors

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    FakeUser,
    admin_actor,
    api_call,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

COMPANY_FULL = {
    "legal_name": "Brazos Bend Utility District No. 1",
    "dba_name": "Brazos Bend Utilities",
    "ein": "74-3182640",
    "state_utility_id": "TX CCN 13148 / PUCT 10238",
    "mailing_address": "9410 FM 1093 Rd, Katy, TX 77494",
    "support_phone": "+1 (281) 555-0164",
    "support_email": "help@brazosbendutilities.com",
    "website": "brazosbendutilities.com",
    "brand_primary_hex": "#1B5E9E",
    "brand_accent_hex": "#201E1D",
    "remit_to_address": "PO Box 2210, Katy, TX 77492",
    "remit_payable_to": "Brazos Bend Utilities",
    "service_hours": "Mon-Fri 8-5 CT",
}

REGIONAL_TX = {
    "country": "United States",
    "state": "Texas",
    "timezone": "America/Chicago",
    "language": "en-US",
    "first_day_of_week": "sunday",
    "currency": "USD",
    "number_format": "1,234.56",
    "date_format": "MM/DD/YYYY",
    "time_format": "12-hour",
    "fy_start_month": 10,
    "fy_start_day": 1,
    "accounting_method": "accrual",
    "close_cadence": "monthly",
    "close_day": "3rd business day",
    "lock_closed_periods": True,
}


# ── US-TEN-005 — Company profile ────────────────────────────────────────────
def test_us_ten_005_tc1__full_tab_save_persists_with_one_audit_row(
    growth_plan, identity_seam, audit_rows
):
    tenant, _ = provisioned_tenant()
    audit_rows.clear()
    actor = admin_actor()
    with tenant_ctx(tenant):
        result = services.save_company_profile(actor, COMPANY_FULL)
    assert result["legal_name"] == COMPANY_FULL["legal_name"]
    assert result["ein"] == "74-3182640"  # displayed NN-NNNNNNN (BR-TEN-018)
    stored = models.Tenant.objects.get(pk=tenant.pk)
    assert stored.ein == "743182640"  # stored as 9 digits
    saves = [r for r in audit_rows if r["action"] == "settings.company_profile.updated"]
    assert len(saves) == 1  # BR-TEN-024: whole tab = ONE audit row
    assert saves[0]["actor_user_id"] == actor.id
    # ⚠ THIS READ `assert saves[0]["before"]["legal_name"] is None` and had been
    # RED since 2026-08-26 (DEF-2510). Provisioning seeds `legal_name` from the
    # signup name, so `before` is "Brazos Bend Utilities" and not NULL — a fact
    # about the FIXTURE, never about the rule this case is here for. What TC-1
    # actually defends is that the audit row records the true prior value, so
    # the case now asserts THAT: `before` is what was stored, `after` is what
    # was saved, and the two differ. Pinning a NULL pinned a provisioning
    # detail that was free to change and did.
    assert saves[0]["before"]["legal_name"] == "Brazos Bend Utilities"
    assert saves[0]["after"]["legal_name"] == COMPANY_FULL["legal_name"]
    assert saves[0]["before"]["legal_name"] != saves[0]["after"]["legal_name"], (
        "the trail must record a CHANGE — a before that equals the after is a "
        "row that proves nothing (BR-TEN-024)"
    )
    # BR-AUD-006: EIN enters the trail MASKED only
    assert saves[0]["after"]["ein"] == "**-***2640"
    assert "743182640" not in str(saves[0])


def test_us_ten_005_tc3__remit_to_edit_is_forward_only_storage_wise(
    growth_plan, identity_seam, audit_rows
):
    """Tenancy's half of BR-TEN-017: the edit changes ONLY the profile column —
    document stamping/re-render is the issuing modules' story (skip-until-wired
    there). The audit trail keeps the before value for the stub-visible proof."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_company_profile(admin_actor(), {"remit_to_address": "Old PO Box 1"})
        audit_rows.clear()
        services.save_company_profile(
            admin_actor(), {"remit_to_address": "PO Box 2210, Katy, TX 77492"}
        )
    row = [r for r in audit_rows if r["action"] == "settings.company_profile.updated"][0]
    assert row["before"]["remit_to_address"] == "Old PO Box 1"
    assert row["after"]["remit_to_address"] == "PO Box 2210, Katy, TX 77492"


@pytest.mark.parametrize("bad_ein", ["74-31826", "743182640X", "7431826400", "74-318264"])
def test_us_ten_005_tc4__bad_ein_rejected_inline(growth_plan, identity_seam, bad_ein):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.save_company_profile(admin_actor(), {"ein": bad_ein})
    fields = {fe["field"] for fe in excinfo.value.field_errors}
    assert fields == {"ein"}
    assert excinfo.value.field_errors[0]["message_key"] == "settings.company.ein_format"


def test_us_ten_005_tc4b__bad_hex_and_email_rejected(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError):
            services.save_company_profile(admin_actor(), {"brand_primary_hex": "1B5E9E"})
        with pytest.raises(errors.ValidationError):
            services.save_company_profile(admin_actor(), {"support_email": "not-an-email"})


# ── US-TEN-005 TC-5 — logo upload (BR-TEN-019), built 2026-08-09 ────────────
PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
HOSTILE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    "<script>alert(document.cookie)</script>"
    '<rect width="64" height="64" fill="#1B5E9E" onload="steal()" onclick="x()"/>'
    '<image href="https://evil.example/pixel.png" x="0" y="0"/>'
    '<a href="javascript:alert(1)"><text x="4" y="20">BBU</text></a>'
    '<circle cx="32" cy="32" r="8" fill="url(https://evil.example/paint)"/>'
    '<use href="#glyph"/><path d="M0 0h64v64H0z" style="fill:url(data:image/svg+xml;base64,x)"/>'
    "</svg>"
).encode()
DOCX_BYTES = b"PK\x03\x04\x14\x00\x06\x00" + b"word/document.xml" + b"\x00" * 64


def _upload(tenant, content, *, name, content_type, role="system_admin"):
    """POST /settings/company/logo the way the wired stack would."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    upload = SimpleUploadedFile(name, content, content_type=content_type)
    return api_call(
        api.company_logo,
        "post",
        user=FakeUser(),
        role=role,
        tenant=tenant,
        data={"file": upload},
        body_format="multipart",
    )


def test_us_ten_005_tc5__valid_png_is_stored_with_a_reference_and_one_audit_row(
    growth_plan, identity_seam, audit_rows
):
    tenant, _ = provisioned_tenant()
    audit_rows.clear()
    response = _upload(tenant, PNG_1PX, name="bbu-logo.png", content_type="image/png")
    assert response.status_code == 201
    assert response.data["content_type"] == "image/png"
    assert response.data["size_bytes"] == len(PNG_1PX)
    # ⚠ AMENDED 2026-10-05 (`CR-172-BRC10`): the reference is the logo's stored
    # document in the common store, and the ROW holds no bytes — it said
    # `startswith("sha256:")` and `bytes(stored.logo_bytes) == PNG_1PX` until then.
    stored = models.Tenant.objects.get(pk=tenant.pk)
    assert response.data["logo_file_id"] == stored.logo_file_id
    assert stored.logo_bytes is None
    assert stored.logo_content_type == "image/png"
    with tenant_ctx(tenant):
        assert selectors.logo_bytes()[0] == PNG_1PX
    rows = [r for r in audit_rows if r["action"] == "settings.company_logo.updated"]
    assert len(rows) == 1  # BR-TEN-016
    assert rows[0]["after"]["logo_file_id"] == response.data["logo_file_id"]
    assert "logo_bytes" not in str(rows[0])  # the trail carries the reference, not the file
    with tenant_ctx(tenant):
        profile = selectors.company_profile()
    assert profile["logo"]["content_type"] == "image/png"


def test_us_ten_005_tc5__oversized_upload_is_refused_413_and_nothing_is_stored(
    growth_plan, identity_seam
):
    """BR-TEN-019 "max 2 MB" rendered as B12 r1's 413 upload-cap row."""
    tenant, _ = provisioned_tenant()
    oversized = PNG_1PX + b"\x00" * (2 * 1024 * 1024)
    response = _upload(tenant, oversized, name="huge.png", content_type="image/png")
    assert response.status_code == 413
    assert response.data["code"] is None  # 413 has no B12 §3 catalog code
    assert response.data["br_ref"] == "BR-TEN-019"
    assert response.data["params"]["max_bytes"] == 2 * 1024 * 1024
    assert models.Tenant.objects.get(pk=tenant.pk).logo_bytes is None


@pytest.mark.parametrize(
    "name,content_type",
    [
        ("policy.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("logo.gif", "image/gif"),
        ("logo.png", "text/html"),  # extension and declared type disagree
    ],
)
def test_us_ten_005_tc5__non_allowlisted_upload_is_refused_415(
    growth_plan, identity_seam, name, content_type
):
    tenant, _ = provisioned_tenant()
    response = _upload(tenant, DOCX_BYTES, name=name, content_type=content_type)
    assert response.status_code == 415  # B12 r1: upload type not allowlisted
    assert response.data["code"] is None
    assert response.data["params"]["allowed"] == ["image/jpeg", "image/png"]  # DEF-TEN-10618
    assert models.Tenant.objects.get(pk=tenant.pk).logo_content_type is None


def test_us_ten_005_tc5__a_renamed_docx_declared_png_is_refused_on_its_bytes(
    growth_plan, identity_seam
):
    """The allowlist is not the whole law: content must BE what it claims."""
    tenant, _ = provisioned_tenant()
    response = _upload(tenant, DOCX_BYTES, name="logo.png", content_type="image/png")
    assert response.status_code == 422 and response.data["code"] == "VAL-002"
    assert response.data["message_key"] == "settings.company.logo_content_mismatch"
    assert models.Tenant.objects.get(pk=tenant.pk).logo_bytes is None


def test_us_ten_005_tc5__a_hostile_svg_is_refused_and_nothing_is_stored(growth_plan, identity_seam):
    """TC-5's *".svg containing <script>"* — neither is stored. Since
    2026-10-27 (`DEF-TEN-10618`, BR-TEN-019 SUPERSEDED, PO *"Allow PNG, JPG"*)
    an SVG is refused outright rather than sanitised; the sanitiser survives
    only for logos already stored (`logo.clean_legacy_svg`), proved below."""
    tenant, _ = provisioned_tenant()
    response = _upload(tenant, HOSTILE_SVG, name="bbu-logo.svg", content_type="image/svg+xml")
    assert response.status_code == 415
    assert response.data["message_key"] == "settings.company.logo_svg_not_accepted"
    assert models.Tenant.objects.get(pk=tenant.pk).logo_file_id is None


def test_us_ten_005_tc5__the_legacy_sanitiser_still_cleans_a_stored_svg():
    """The script, every on* handler, the external image, the javascript: link
    and the remote url() paint are all gone; the artwork and the in-document
    reference survive. Only a logo stored before 2026-10-27 meets this."""
    from apps.tenancy import logo

    stored = logo.clean_legacy_svg(HOSTILE_SVG).decode()
    for payload in ("script", "onload", "onclick", "javascript:", "evil.example", "<image", "<a "):
        assert payload not in stored
    assert "data:image/svg+xml" not in stored
    assert 'fill="#1B5E9E"' in stored  # the actual logo survives
    assert 'viewBox="0 0 64 64"' in stored
    assert 'href="#glyph"' in stored  # in-document reference is legitimate


def test_us_ten_005_tc5__the_legacy_sanitiser_refuses_a_dtd_outright():
    """Entity expansion (XXE / billion laughs) is refused, not stripped."""
    from apps.tenancy import logo
    from core import errors as core_errors

    bomb = (
        '<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        '<svg xmlns="http://www.w3.org/2000/svg"><text>&xxe;</text></svg>'
    ).encode()
    with pytest.raises(core_errors.ValidationError) as caught:
        logo.clean_legacy_svg(bomb)
    assert caught.value.message_key == "settings.company.logo_svg_dtd_forbidden"


def test_us_ten_005_tc5__clerk_cannot_upload_a_logo(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    denied = _upload(
        tenant, PNG_1PX, name="bbu-logo.png", content_type="image/png", role="billing_clerk"
    )
    assert denied.status_code == 403 and denied.data["code"] == "AUTH-002"


def test_us_ten_005_tc5__the_same_law_refuses_a_non_http_caller(growth_plan, identity_seam):
    """The 413/415 are the transport rendering; a job or shell caller meets the
    identical refusal as a 422 catalog error (services re-checks everything)."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError):
            services.save_company_logo(
                admin_actor(), DOCX_BYTES, content_type="application/msword", filename="x.doc"
            )
        with pytest.raises(errors.ValidationError):
            services.save_company_logo(
                admin_actor(),
                PNG_1PX + b"\x00" * (2 * 1024 * 1024),
                content_type="image/png",
                filename="huge.png",
            )
    assert models.Tenant.objects.get(pk=tenant.pk).logo_bytes is None


def test_us_ten_005_tc7__company_values_are_per_tenant(growth_plan, identity_seam):
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    with tenant_ctx(brazos):
        services.save_company_profile(admin_actor(), {"ein": "74-3182640"})
    with tenant_ctx(lonestar):
        profile = selectors.company_profile()
    assert profile["ein"] is None  # Brazos Bend's EIN never readable cross-tenant
    # (RLS FORCE half = G5 isolation suite)


def test_us_ten_005_api__clerk_denied_admin_saves(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    denied = api_call(
        api.company_settings,
        "put",
        user=FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        data={"dba_name": "X"},
    )
    assert denied.status_code == 403 and denied.data["code"] == "AUTH-002"
    saved = api_call(
        api.company_settings,
        "put",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        data={"dba_name": "Brazos Bend Utilities"},
    )
    assert saved.status_code == 200
    assert saved.data["dba_name"] == "Brazos Bend Utilities"


# ── US-TEN-006 — Regional, formats & fiscal ─────────────────────────────────
def test_us_ten_006_tc1__tx_defaults_save_and_read_back(growth_plan, identity_seam, audit_rows):
    tenant, _ = provisioned_tenant()
    audit_rows.clear()
    with tenant_ctx(tenant):
        result = services.save_regional_settings(admin_actor(), REGIONAL_TX)
    assert result["timezone"] == "America/Chicago"
    assert result["currency"] == "USD"
    assert result["first_day_of_week"] == "sunday"
    assert result["lock_closed_periods"] is True
    saves = [r for r in audit_rows if r["action"] == "settings.regional_fiscal.updated"]
    assert len(saves) == 1  # one atomic tab save, one audit row


def test_us_ten_006_tc2__format_change_never_touches_stored_values(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_regional_settings(admin_actor(), REGIONAL_TX)
        before = models.NumberSeries.objects.filter(tenant=tenant).count()
        before_uoms = list(models.Uom.objects.filter(tenant=tenant).values_list("code", "name"))
        services.save_regional_settings(admin_actor(), {"date_format": "YYYY-MM-DD"})
        # BR-TEN-020: display-time transform only — stored rows bit-identical
        assert models.NumberSeries.objects.filter(tenant=tenant).count() == before
        assert (
            list(models.Uom.objects.filter(tenant=tenant).values_list("code", "name"))
            == before_uoms
        )
        assert selectors.regional_settings()["date_format"] == "YYYY-MM-DD"


def test_us_ten_006_tc3__current_period_card_computed_from_fiscal_fields(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_regional_settings(admin_actor(), REGIONAL_TX)
        card = selectors.current_period(reference_date=date(2026, 8, 8))
    # "FY2026 · Period 11 — Aug 1 to Aug 31 · Open · closes Sep 3, 2026"
    assert card == {
        "fy_label": "FY2026",
        "period": 11,
        "start": "2026-08-01",
        "end": "2026-08-31",
        "status": "open",
        "close_by": "2026-09-03",
    }


def test_us_ten_006_tc4__currency_locked_once_financial_records_exist(
    growth_plan, identity_seam, monkeypatch
):
    """BR-TEN-042 (newest-wins over the epic's warn-and-confirm TC — E2 reported):
    once a financial record exists the change is a 409 BIZ-LOCKED."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        # pre-lock: forward-only change is allowed (BR-TEN-021)
        result = services.save_regional_settings(admin_actor(), {"currency": "CAD"})
        assert result["currency"] == "CAD"
        # first financial record exists → LOCKED
        monkeypatch.setattr(
            billing_services, "financial_records_exist", lambda: True, raising=False
        )
        with pytest.raises(errors.BizError) as excinfo:
            services.save_regional_settings(admin_actor(), {"currency": "USD"})
    assert excinfo.value.code == errors.BIZ_LOCKED
    assert excinfo.value.http_status == 409
    assert excinfo.value.br_ref == "BR-TEN-042"
    assert models.Tenant.objects.get(pk=tenant.pk).currency == "CAD"  # unchanged


def test_us_ten_006_tc5__invalid_fy_day_combination_rejected(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.save_regional_settings(
                admin_actor(), {"fy_start_month": 2, "fy_start_day": 30}
            )
    assert {fe["field"] for fe in excinfo.value.field_errors} == {"fy_start_day"}


def test_us_ten_006_tc6__language_set_follows_br_ten_042(growth_plan, identity_seam):
    """LC-2 seeded languages are selectable (es included — supersedes the epic's
    'Español coming soon' TC, E2 reported); outside the set → 422."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        result = services.save_regional_settings(admin_actor(), {"language": "es"})
        assert result["language"] == "es"
        with pytest.raises(errors.ValidationError):
            services.save_regional_settings(admin_actor(), {"language": "fr"})


def test_us_ten_006_tc7__regional_settings_are_per_tenant(growth_plan, identity_seam):
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    with tenant_ctx(brazos):
        services.save_regional_settings(admin_actor(), {"time_format": "24-hour"})
    with tenant_ctx(lonestar):
        services.save_regional_settings(admin_actor(), {"time_format": "12-hour"})
        assert selectors.regional_settings()["time_format"] == "12-hour"
    with tenant_ctx(brazos):
        assert selectors.regional_settings()["time_format"] == "24-hour"

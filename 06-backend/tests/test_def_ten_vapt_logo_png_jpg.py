# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-TEN-10618 — VAPT stored-XSS finding (SVG logo upload).
# Ruling:   decision log 2026-10-27 "VAPT round: five findings ruled" (1):
#           BR-TEN-019 SUPERSEDED — company logos are PNG or JPG only; SVG is
#           refused in the browser and on the server; stored SVG logos keep
#           their already-sanitised PNG copy.
# Doc:      09-infra/06-vapt-remediation-2026-10.md §1, Test table rows 2–4.
# ───────────────────────────────────────────────────────
"""PNG or JPG only. Red first, without the change:

  * SVG     — an SVG upload is ACCEPTED (201) and sanitised; nothing refuses it.
  * RENAME  — an SVG renamed `.png` is refused only by accident of the PNG
              signature check; a `.jpg` one is refused 415 as an unknown type
              rather than on its contents.
  * JPG     — `image/jpeg` is not on the allowlist (415), so no JPG can be a
              logo and no JPG ever printed on a bill.
  * LEGACY  — a utility whose stored logo is an SVG is served the SVG itself.
"""

import hashlib
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.tenancy import api, logo, models, selectors
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import FakeUser, admin_actor, api_call, provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db

SVG_KEY = "settings.company.logo_svg_not_accepted"

SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="48" viewBox="0 0 120 48">'
    b'<rect width="120" height="48" fill="#0F7A6B"/><script>alert(1)</script></svg>'
)


def _image(fmt: str, colour=(27, 94, 158), size=(60, 24)) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format=fmt)
    return buffer.getvalue()


PNG = _image("PNG")
JPG = _image("JPEG")


def _upload(tenant, content, name, content_type):
    return api_call(
        api.company_logo,
        "post",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        data={"file": SimpleUploadedFile(name, content, content_type=content_type)},
        body_format="multipart",
    )


def _read(tenant):
    return api_call(api.company_logo_file, "get", user=FakeUser(), role="system_admin", tenant=tenant)


# ══ SVG · refused by the server, by type and by name ═══════════════════════
@pytest.mark.parametrize(
    "name,content_type",
    [
        ("logo.svg", "image/svg+xml"),  # the honest case
        ("logo.svg", "application/octet-stream"),  # a browser that sends no type
        ("logo.svg", ""),
        ("logo", "image/svg+xml"),  # no extension at all
    ],
)
def test_def_ten_10618__an_svg_upload_is_refused_415_with_its_own_sentence(
    growth_plan, identity_seam, name, content_type
):
    tenant, _ = provisioned_tenant()
    response = _upload(tenant, SVG, name, content_type)
    assert response.status_code == 415, response.data
    assert response.data["message_key"] == SVG_KEY
    assert response.data["code"] is None
    tenant.refresh_from_db()
    assert tenant.logo_file_id is None and tenant.logo_content_type is None


def test_def_ten_10618__the_service_refuses_an_svg_from_a_non_http_caller(
    growth_plan, identity_seam
):
    from apps.tenancy import services
    from core import errors

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant), pytest.raises(errors.ValidationError) as caught:
        services.save_company_logo(
            admin_actor(), SVG, content_type="image/svg+xml", filename="x.svg"
        )
    assert caught.value.message_key == SVG_KEY


def test_def_ten_10618__the_allowlist_is_png_and_jpeg_only():
    assert sorted(logo.LOGO_CONTENT_TYPES) == ["image/jpeg", "image/png"]


# ══ RENAME · contents are checked, not the name ═══════════════════════════
@pytest.mark.parametrize(
    "name,content_type",
    [("evil.png", "image/png"), ("evil.jpg", "image/jpeg"), ("evil.jpeg", "image/jpeg")],
)
def test_def_ten_10618__an_svg_renamed_png_or_jpg_is_refused_on_its_bytes(
    growth_plan, identity_seam, name, content_type
):
    tenant, _ = provisioned_tenant()
    response = _upload(tenant, SVG, name, content_type)
    assert response.status_code == 422, response.data
    assert response.data["message_key"] == "settings.company.logo_content_mismatch"
    tenant.refresh_from_db()
    assert tenant.logo_file_id is None


def test_def_ten_10618__a_png_declared_jpeg_is_refused_on_its_bytes(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    response = _upload(tenant, PNG, "logo.jpg", "image/jpeg")
    assert response.status_code == 422
    assert response.data["message_key"] == "settings.company.logo_content_mismatch"


# ══ JPG · accepted, drawn on screen, and printed ══════════════════════════
@pytest.mark.parametrize("name", ["logo.jpg", "logo.jpeg"])
def test_def_ten_10618__a_jpg_is_accepted_and_served_as_uploaded(growth_plan, identity_seam, name):
    tenant, _ = provisioned_tenant()
    response = _upload(tenant, JPG, name, "image/jpeg")
    assert response.status_code == 201, response.data
    assert response.data["content_type"] == "image/jpeg"
    read = _read(tenant)
    assert read.status_code == 200
    assert read["Content-Type"] == "image/jpeg"
    assert read.content == JPG


def test_def_ten_10618__a_jpg_gets_a_png_copy_for_print(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    assert _upload(tenant, JPG, "logo.jpg", "image/jpeg").status_code == 201
    with tenant_ctx(tenant):
        stamped = selectors.bill_logo()
        assert stamped is not None, "a JPG logo stamps nothing on a bill"
        png = selectors.logo_png_for_documents(stamped["document_id"])
    assert stamped["content_type"] == "image/png"
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    from PIL import Image

    printed = Image.open(io.BytesIO(png))
    assert printed.size == (60, 24)


def test_def_ten_10618__a_png_is_still_accepted(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    assert _upload(tenant, PNG, "logo.png", "image/png").status_code == 201
    assert _read(tenant).content == PNG


# ══ LEGACY · a stored SVG logo is served as its PNG copy ══════════════════
def _legacy_svg(tenant):
    cleaned = logo.clean_legacy_svg(SVG)
    models.Tenant.objects.filter(pk=tenant.pk).update(
        logo_bytes=cleaned,
        logo_content_type="image/svg+xml",
        logo_file_id="sha256:" + hashlib.sha256(cleaned).hexdigest(),
    )
    return cleaned


def test_def_ten_10618__a_stored_svg_logo_is_served_as_its_png_copy(growth_plan, identity_seam):
    from apps.tenancy import services

    tenant, _ = provisioned_tenant()
    _legacy_svg(tenant)
    assert services.move_logos_to_store()["moved"] == 1  # the existing data is kept, not deleted
    read = _read(tenant)
    assert read.status_code == 200
    assert read["Content-Type"] == "image/png"
    assert read.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"<svg" not in read.content


def test_def_ten_10618__a_stored_svg_not_yet_moved_is_still_served_as_png(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    _legacy_svg(tenant)
    read = _read(tenant)
    assert read.status_code == 200
    assert read["Content-Type"] == "image/png"
    assert read.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_def_ten_10618__the_svg_sentence_is_in_all_eleven_catalogues():
    import json
    import pathlib

    locales = pathlib.Path(__file__).resolve().parents[2] / "07-frontend/src/i18n/locales"
    files = sorted(locales.glob("*.json"))
    assert len(files) == 11
    for path in files:
        catalogue = json.loads(path.read_text(encoding="utf-8"))
        assert catalogue.get(SVG_KEY), path.name
    english = json.loads((locales / "en.json").read_text(encoding="utf-8"))
    assert english[SVG_KEY] == "SVG files aren't accepted. Use PNG or JPG."
    assert english["settings.company.logo.drop"] == "Logo — PNG or JPG, max 2 MB"

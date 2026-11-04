# ── Trace ──────────────────────────────────────────────
# Change:   CR-172-BRC10 — the utility logo moves from a database column into
#           the S3 document store, and is drawn everywhere it belongs.
# Defects:  DEF-TEN-9704 (broken image on two-host deployments — the cause is
#           the front end's address; its test is BrandMark.test.tsx) ·
#           DEF-TEN-9705 (four surfaces never drew the logo).
# Rules:    BR-TEN-019 (SVG/PNG ≤ 2 MB, SVG sanitised, rasterised for print) ·
#           BR-TEN-017 (stamped at issue, never re-rendered) · BR-BIL-030 ·
#           NFR-33 (a logo is a STORED ARTIFACT) · CLAUDE.md hard rules 1 & 7 ·
#           hard-won law 14 (the migration is proved on PostgreSQL).
# ───────────────────────────────────────────────────────
"""The logo lives in the common document store, and only its reference on the row.

What each block fails on without the change — written red first:

  * STORE    — `tenants.logo_bytes` is written and no `stored_documents` row
               exists; `kind="tenant_logo"` is refused by the store's own list.
  * S3       — the object never reaches the bucket.
  * RASTER   — an SVG has no PNG beside it; nothing in the backend could make one.
  * READ     — the route reads the column, so emptying it 404s every logo.
  * DOWN     — a storage failure is not refused in words; the row is written.
  * MOVE     — no function moves an existing logo; the bytes stay on the row.
  * BILL     — a bill stamps no logo and its PDF holds no image.
"""

import hashlib
import io
import re
import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.tenancy import api, document_storage, logo, models, selectors
from apps.tenancy.document_models import StoredDocument
from core import tenancy as core_tenancy
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


def _png(colour=(27, 94, 158), size=(60, 24)) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


PNG_A = _png()
PNG_B = _png((196, 40, 28))
SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="48" viewBox="0 0 120 48">'
    b'<rect width="120" height="48" fill="#0F7A6B"/><circle cx="24" cy="24" r="14" '
    b'fill="#F5E9A0"/><script>alert(1)</script></svg>'
)


def _upload(tenant, content=PNG_A, name="logo.png", content_type="image/png", role="system_admin"):
    return api_call(
        api.company_logo,
        "post",
        user=FakeUser(),
        role=role,
        tenant=tenant,
        data={"file": SimpleUploadedFile(name, content, content_type=content_type)},
        body_format="multipart",
    )


def _read(tenant, *, user=FakeUser(), role="system_admin", headers=None):
    return api_call(
        api.company_logo_file, "get", user=user, role=role, tenant=tenant, headers=headers
    )


def _docs(tenant):
    return list(
        StoredDocument.objects.filter(tenant_id=tenant.id, kind="tenant_logo").order_by(
            "stored_at", "content_type"
        )
    )


@pytest.fixture()
def s3(settings):
    """The REAL S3 adapter against moto — the bytes go through boto3, not disk."""
    import boto3
    from moto import mock_aws

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="sbh-logo-test")
        settings.DOCUMENT_STORAGE_BACKEND = "aws_s3"
        settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = False
        settings.DOCUMENT_STORAGE_BUCKET = "sbh-logo-test"
        settings.DOCUMENT_STORAGE_REGION = "us-east-1"
        settings.DOCUMENT_STORAGE_SSE = "AES256"
        settings.DOCUMENT_STORAGE_OBJECT_LOCK_MODE = "NONE"
        document_storage.set_s3_client_factory(lambda: client)
        try:
            yield client
        finally:
            document_storage.set_s3_client_factory(None)


@pytest.fixture()
def storage_down(settings):
    """A deployment whose store cannot be used — no bucket named."""
    settings.DOCUMENT_STORAGE_BACKEND = "aws_s3"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = False
    settings.DOCUMENT_STORAGE_BUCKET = ""
    yield


# ══ STORE · the upload goes through the common store ═══════════════════════
def test_cr172_upload__stores_through_the_document_store_and_keeps_only_the_reference(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    response = _upload(tenant)
    assert response.status_code == 201, response.data

    tenant.refresh_from_db()
    assert tenant.logo_bytes is None, "the bytes stayed on the row"
    docs = _docs(tenant)
    assert len(docs) == 1
    assert tenant.logo_file_id == str(docs[0].id)
    assert tenant.logo_content_type == "image/png"
    assert docs[0].content_hash == hashlib.sha256(PNG_A).hexdigest()
    assert response.data["logo_file_id"] == str(docs[0].id)


def test_cr172_upload__the_key_is_the_cr160_path_in_the_tenancy_folder(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    _upload(tenant)
    doc = _docs(tenant)[0]
    assert re.fullmatch(
        rf"t/{tenant.subdomain}/tenancy/\d{{4}}/\d{{2}}/{doc.id}\.png", doc.storage_key
    ), doc.storage_key


def test_cr172_upload__lands_in_s3(growth_plan, identity_seam, s3):
    tenant, _ = provisioned_tenant()
    assert _upload(tenant).status_code == 201
    doc = _docs(tenant)[0]
    assert doc.storage_backend == "aws_s3"
    body = s3.get_object(Bucket="sbh-logo-test", Key=doc.storage_key)["Body"].read()
    assert body == PNG_A
    assert _read(tenant).content == PNG_A


def test_cr172_upload__the_sanitiser_is_still_the_only_way_in(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    big = b"\x89PNG\r\n\x1a\n" + b"0" * (logo.LOGO_MAX_BYTES + 1)
    assert _upload(tenant, big).status_code == 413
    assert _upload(tenant, b"%PDF-1.4", name="x.pdf", content_type="application/pdf").status_code == 415
    assert _upload(tenant, b"not a png", name="x.png").status_code == 422
    assert _docs(tenant) == [], "a refused upload stored something"


# ══ RASTER · an SVG is cleaned, and rendered to PNG for print ══════════════
def test_cr172_svg__stored_cleaned_with_a_png_rendering_beside_it(growth_plan, identity_seam):
    """⚠ AN SVG IS NO LONGER UPLOADED (`DEF-TEN-10618`, PO 2026-10-27, *"Allow
    PNG, JPG"*) — so this is a utility whose SVG was stored BEFORE the ruling,
    moved into the store, and now SERVED AS ITS PNG COPY, never the SVG."""
    from apps.tenancy import services

    tenant, _ = provisioned_tenant()
    _legacy(tenant, logo.clean_legacy_svg(SVG), "image/svg+xml")
    assert services.move_logos_to_store()["moved"] == 1
    svg_doc, png_doc = sorted(_docs(tenant), key=lambda d: d.content_type, reverse=True)
    assert svg_doc.content_type == "image/svg+xml"
    assert png_doc.content_type == "image/png"
    assert svg_doc.source_id == png_doc.source_id, "two representations of ONE logo"
    tenant.refresh_from_db()
    assert tenant.logo_file_id == str(svg_doc.id)

    with tenant_ctx(tenant):
        from apps.tenancy import document_store

        stored_svg = document_store.fetch(svg_doc.id)
        raster = document_store.fetch(png_doc.id)
    assert b"<script" not in stored_svg
    assert raster.startswith(b"\x89PNG\r\n\x1a\n")
    # DEF-TEN-10618: the screen is served the PNG copy, not the SVG.
    read = _read(tenant)
    assert read["Content-Type"] == "image/png"
    assert read.content == raster


def test_cr172_raster__renders_a_real_picture():
    png = logo.raster_png(logo.clean_legacy_svg(SVG))
    from PIL import Image

    image = Image.open(io.BytesIO(png))
    assert image.width >= 240 and image.height >= 96
    # The teal rectangle is drawn, not a transparent canvas.
    assert image.convert("RGB").getpixel((image.width - 4, 4)) == (15, 122, 107)


# ══ READ · one address, the reference in its cache key ═════════════════════
def test_cr172_read__serves_from_the_store_and_the_etag_is_the_reference(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    _upload(tenant)
    tenant.refresh_from_db()
    first = _read(tenant)
    assert first.status_code == 200
    assert first.content == PNG_A
    assert first["ETag"] == f'"{tenant.logo_file_id}"'
    assert _read(tenant, headers={"If-None-Match": first["ETag"]}).status_code == 304


def test_cr172_replace__a_new_upload_is_a_new_reference_and_a_new_etag(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    _upload(tenant, PNG_A)
    before = _read(tenant)
    _upload(tenant, PNG_B)
    after = _read(tenant, headers={"If-None-Match": before["ETag"]})
    assert after.status_code == 200, "the old ETag still matched — the browser keeps the old logo"
    assert after.content == PNG_B
    assert after["ETag"] != before["ETag"]
    assert len(_docs(tenant)) == 2, "the replaced logo is kept (write-once), not deleted"


def test_cr172_read__needs_no_sign_in_but_the_upload_does(growth_plan, identity_seam):
    """The logo is on every bill and on the public portal; the read is public
    and scoped to the utility in the address. The write is System Admin only."""
    tenant, _ = provisioned_tenant()
    _upload(tenant)
    anonymous = api_call(api.company_logo_file, "get", tenant=tenant)
    assert anonymous.status_code == 200
    assert anonymous.content == PNG_A
    assert _upload(tenant, PNG_B, role="billing_clerk").status_code == 403


def test_cr172_profile_and_shell__publish_the_reference_for_the_cache_key(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    _upload(tenant)
    tenant.refresh_from_db()
    with tenant_ctx(tenant):
        profile = selectors.company_profile()
        shell = selectors.shell_display()
    assert profile["logo"]["logo_file_id"] == tenant.logo_file_id
    assert profile["logo"]["size_bytes"] == len(PNG_A)
    assert shell["company"]["logo_ref"] == tenant.logo_file_id


# ══ DOWN · storage unavailable refuses in words and saves nothing ══════════
def test_cr172_storage_down__refuses_with_a_clear_message_and_saves_nothing(
    growth_plan, identity_seam, storage_down
):
    tenant, _ = provisioned_tenant()
    response = _upload(tenant)
    assert response.status_code == 503, response.data
    assert response.data["message_key"] == "settings.company.logo_storage_unavailable"
    tenant.refresh_from_db()
    assert tenant.logo_file_id is None and tenant.logo_bytes is None
    assert _docs(tenant) == []


def test_cr172_storage_down__a_refused_write_is_refused_the_same_way(
    growth_plan, identity_seam, s3, settings
):
    tenant, _ = provisioned_tenant()
    settings.DOCUMENT_STORAGE_BUCKET = "no-such-bucket"
    response = _upload(tenant)
    assert response.status_code == 503, response.data
    assert response.data["message_key"] == "settings.company.logo_storage_unavailable"
    tenant.refresh_from_db()
    assert tenant.logo_file_id is None


def test_cr172_storage_down__the_message_is_in_all_eleven_catalogues():
    import json
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
    files = sorted(root.glob("*.json"))
    assert len(files) == 11
    for path in files:
        catalogue = json.loads(path.read_text(encoding="utf-8"))
        assert catalogue.get("settings.company.logo_storage_unavailable"), path.name


# ══ ISOLATION · one utility never reaches another's logo ═══════════════════
def test_cr172_isolation__each_address_serves_only_its_own_utility(growth_plan, identity_seam):
    brazos, _ = provisioned_tenant(brazosbend_payload())
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    _upload(brazos, PNG_A)
    _upload(lonestar, PNG_B)
    assert _read(brazos).content == PNG_A
    assert _read(lonestar).content == PNG_B
    lonestar.refresh_from_db()
    # Lone Star's stored document cannot be resolved under Brazos's context.
    from apps.tenancy import document_store

    with tenant_ctx(brazos):
        with pytest.raises(document_store.DocumentStoreError):
            document_store.fetch(lonestar.logo_file_id)


@pytest.mark.isolation
@requires_postgres
def test_cr172_isolation__on_live_postgres(growth_plan, identity_seam):
    brazos, _ = provisioned_tenant(brazosbend_payload())
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    _upload(brazos, PNG_A)
    _upload(lonestar, PNG_B)
    lonestar.refresh_from_db()
    from apps.tenancy import document_store

    with live_tenant_context(brazos.id):
        assert selectors.logo_bytes()[0] == PNG_A
        with pytest.raises(document_store.DocumentStoreError):
            document_store.fetch(lonestar.logo_file_id)
    with live_tenant_context(lonestar.id):
        assert selectors.logo_bytes()[0] == PNG_B


# ══ MOVE · existing logos are copied, proved, repointed — and re-runnable ══
def _legacy(tenant, content=PNG_A, content_type="image/png"):
    """A row exactly as the old build left it: bytes on the row, sha256 ref."""
    models.Tenant.objects.filter(pk=tenant.pk).update(
        logo_bytes=content,
        logo_content_type=content_type,
        logo_file_id="sha256:" + hashlib.sha256(content).hexdigest(),
    )


def test_cr172_move__copies_proves_and_repoints(growth_plan, identity_seam):
    from apps.tenancy import services

    tenant, _ = provisioned_tenant()
    _legacy(tenant)
    report = services.move_logos_to_store()
    assert report == {"moved": 1, "already": 0, "left": 0}
    tenant.refresh_from_db()
    assert tenant.logo_bytes is None
    doc = _docs(tenant)[0]
    assert tenant.logo_file_id == str(doc.id)
    assert doc.content_hash == hashlib.sha256(PNG_A).hexdigest()
    assert _read(tenant).content == PNG_A


def test_cr172_move__is_safe_to_run_twice(growth_plan, identity_seam):
    from apps.tenancy import services

    tenant, _ = provisioned_tenant()
    _legacy(tenant)
    services.move_logos_to_store()
    assert services.move_logos_to_store() == {"moved": 0, "already": 1, "left": 0}
    assert len(_docs(tenant)) == 1


def test_cr172_move__an_interrupted_run_reuses_its_copy(growth_plan, identity_seam):
    """Bytes stored, row not yet repointed (the process died between the two):
    the re-run finds the copy by its deterministic source and does not store
    a second one."""
    from apps.tenancy import services

    tenant, _ = provisioned_tenant()
    _legacy(tenant)
    tenant.refresh_from_db()  # the derived source keys on the row's `sha256:` reference
    with tenant_ctx(tenant):
        services._store_logo(PNG_A, "image/png", source_id=services._legacy_logo_source(tenant), process="test")
    assert len(_docs(tenant)) == 1
    assert services.move_logos_to_store()["moved"] == 1
    assert len(_docs(tenant)) == 1


def test_cr172_move__an_svg_gets_its_png_rendering(growth_plan, identity_seam):
    from apps.tenancy import services

    tenant, _ = provisioned_tenant()
    cleaned = logo.clean_legacy_svg(SVG)
    _legacy(tenant, cleaned, "image/svg+xml")
    services.move_logos_to_store()
    assert sorted(d.content_type for d in _docs(tenant)) == ["image/png", "image/svg+xml"]


def test_cr172_move__storage_down_leaves_the_bytes_where_they_are(
    growth_plan, identity_seam, storage_down
):
    from apps.tenancy import services

    tenant, _ = provisioned_tenant()
    _legacy(tenant)
    before = models.Tenant.objects.values("logo_bytes", "logo_file_id").get(pk=tenant.pk)
    assert services.move_logos_to_store() == {"moved": 0, "already": 0, "left": 1}
    after = models.Tenant.objects.values("logo_bytes", "logo_file_id").get(pk=tenant.pk)
    assert bytes(after["logo_bytes"]) == bytes(before["logo_bytes"]) == PNG_A
    assert after["logo_file_id"] == before["logo_file_id"]
    # …and the logo still draws, from the row, until the move is finished.
    assert _read(tenant).content == PNG_A


def test_cr172_move__a_copy_that_does_not_match_is_not_accepted(
    growth_plan, identity_seam, monkeypatch
):
    from apps.tenancy import document_store, services

    tenant, _ = provisioned_tenant()
    _legacy(tenant)
    monkeypatch.setattr(document_store, "fetch", lambda document_id: b"corrupted")
    assert services.move_logos_to_store() == {"moved": 0, "already": 0, "left": 1}
    tenant.refresh_from_db()
    assert bytes(tenant.logo_bytes) == PNG_A
    assert tenant.logo_file_id.startswith("sha256:")


# ══ BILL · the logo it was issued with, drawn as an image ══════════════════
def test_cr172_bill_document_logo__the_published_read_names_the_png(growth_plan, identity_seam):
    """A JPG (`DEF-TEN-10618`) — the upload that has a second, printed copy
    now that an SVG cannot be uploaded."""
    from PIL import Image

    tenant, _ = provisioned_tenant()
    buffer = io.BytesIO()
    Image.new("RGB", (60, 24), (27, 94, 158)).save(buffer, format="JPEG")
    assert _upload(tenant, buffer.getvalue(), name="logo.jpg", content_type="image/jpeg").status_code == 201
    with tenant_ctx(tenant):
        stamped = selectors.bill_logo()
        png = selectors.logo_png_for_documents(stamped["document_id"])
    assert stamped["content_type"] == "image/png"
    assert png.startswith(b"\x89PNG")


@requires_postgres
@pytest.mark.isolation
def test_cr172_move__the_migration_function_on_live_postgres(growth_plan, identity_seam):
    """Hard-won law 14: the move runs per utility inside a savepoint on PostgreSQL."""
    from apps.tenancy import services

    brazos, _ = provisioned_tenant(brazosbend_payload())
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    _legacy(brazos, PNG_A)
    _legacy(lonestar, PNG_B)
    assert services.move_logos_to_store() == {"moved": 2, "already": 0, "left": 0}
    assert services.move_logos_to_store() == {"moved": 0, "already": 2, "left": 0}
    with live_tenant_context(brazos.id):
        assert selectors.logo_bytes()[0] == PNG_A
    with live_tenant_context(lonestar.id):
        assert selectors.logo_bytes()[0] == PNG_B


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-172-BRC10 · decision log 2026-10-05 (two PO rows + "LOGO TO S3 — SIX JUDGMENTS OF OURS")
# generated: 2026-10-05 by lane LOGO
# status: HUMAN-REVIEW-PENDING (the migration it proves is 🔒 migration ordering)
# ──────────────────────────────────────────────────────────

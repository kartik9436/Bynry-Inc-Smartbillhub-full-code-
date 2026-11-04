# ── Trace ──────────────────────────────────────────────
# Change:   CR-172-BRC10 · DEF-TEN-9705 — a generated bill draws the utility's
#           logo, as an image, from the stored document it was STAMPED with.
# Rules:    BR-TEN-017 (stamped at issue; an issued document is never
#           re-rendered with a later logo) · BR-TEN-019 (rasterised for print) ·
#           BR-BIL-030 ("tenant identity and branding reference") · BR-BIL-033.
# ───────────────────────────────────────────────────────
"""The bill carries the logo it was issued with — on the PDF and the HTML.

Red first, without the change: the payload carries no `utility_logo`, the PDF
holds no `/Subtype /Image`, and the HTML no `data:image/png`.
"""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.billing import documents, models
from apps.tenancy import api as tenancy_api
from tests.test_us_bil_022_documents import an_issued_bill
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_005_issue import an_authorised_run
from tests.test_us_ten_helpers import FakeUser, api_call
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db


def _png(colour):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGBA", (90, 30), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(tenant, content, name="logo.png", content_type="image/png"):
    response = api_call(
        tenancy_api.company_logo,
        "post",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        data={"file": SimpleUploadedFile(name, content, content_type=content_type)},
        body_format="multipart",
    )
    assert response.status_code == 201, response.data
    return response


def test_cr172_bill__is_stamped_with_the_logo_and_draws_it_on_both_serialisations(brazos, dana):
    _upload(brazos, _png((27, 94, 158, 255)))
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        stamp = models.Invoice.objects.get(pk=bill.pk).bill_payload["utility_logo"]
        assert stamp and stamp["content_type"] == "image/png"

        rendered = documents.render_invoice(bill)
        assert b"/Subtype /Image" in rendered.pdf
        assert b"/Im1 Do" in rendered.pdf
        assert "data:image/png;base64," in rendered.body
        assert rendered.logo is not None and rendered.logo.document_id == stamp["document_id"]
        # Deterministic still (`test_us_bil_022_tc12`): a reprint is the same bytes.
        assert documents.render_invoice(models.Invoice.objects.get(pk=bill.pk)).pdf == rendered.pdf


def _jpg(colour):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (90, 30), colour).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_def_ten_10618_bill__a_jpg_logo_prints_from_its_png_copy(brazos, dana):
    """`DEF-TEN-10618` (PO 2026-10-27, *"Allow PNG, JPG"*): a JPG logo prints.
    This case was *"an SVG logo prints from its PNG rendering"* until SVG
    uploads were refused; a stored SVG still prints from the same PNG copy
    (`test_cr172_logo_document_store` → the move test)."""
    _upload(brazos, _jpg((15, 122, 107)), name="logo.jpg", content_type="image/jpeg")
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        stamp = models.Invoice.objects.get(pk=bill.pk).bill_payload["utility_logo"]
        assert stamp and stamp["content_type"] == "image/png"
        rendered = documents.render_invoice(bill)
    assert b"/Subtype /Image" in rendered.pdf
    assert "data:image/png;base64," in rendered.body
    assert rendered.logo.png.startswith(b"\x89PNG")


def test_cr172_bill__keeps_the_logo_it_was_issued_with_after_a_replace(brazos, dana):
    """BR-TEN-017: edits affect FUTURE documents only."""
    _upload(brazos, _png((27, 94, 158, 255)))
    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        first = an_issued_bill(brazos, dana, account=an_account(dana, brazos), run=run)
        before = documents.render_invoice(first).logo
    _upload(brazos, _png((196, 40, 28, 255)))
    with tenant_ctx(brazos):
        second = an_issued_bill(
            brazos,
            dana,
            account=an_account(dana, brazos, account_no="A-77"),
            run=run,
            invoice_no="BL-2607-000777",
        )
        again = documents.render_invoice(models.Invoice.objects.get(pk=first.pk)).logo
        after = documents.render_invoice(second).logo
    assert again.document_id == before.document_id
    assert again.png == before.png
    assert after.document_id != before.document_id


def test_cr172_bill__a_bill_without_a_stamp_prints_as_it_always_did(brazos, dana):
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        rendered = documents.render_invoice(bill)
    assert rendered.logo is None
    assert b"/Subtype /Image" not in rendered.pdf
    assert "data:image/png" not in rendered.body


def test_cr172_bill__a_logo_the_store_cannot_return_is_left_off_and_the_bill_prints(
    brazos, dana, monkeypatch
):
    _upload(brazos, _png((27, 94, 158, 255)))
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        from apps.billing import tenancy_seam

        monkeypatch.setattr(tenancy_seam, "logo_png", lambda document_id: None)
        documents._DECODED_LOGOS.clear()
        rendered = documents.render_invoice(models.Invoice.objects.get(pk=bill.pk))
    assert rendered.pdf.startswith(b"%PDF-")
    assert b"/Subtype /Image" not in rendered.pdf


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-172-BRC10 · decision log 2026-10-05 ("LOGO TO S3 — SIX JUDGMENTS OF OURS" (4))
# generated: 2026-10-05 by lane LOGO
# status: HUMAN-REVIEW-PENDING (billing/documents.py and issue.py are 🔒-reviewed files)
# ──────────────────────────────────────────────────────────

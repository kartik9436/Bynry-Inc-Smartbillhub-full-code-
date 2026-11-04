# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-4458 (2026-09-07) — a System Admin chooses the page every
#           customer receives sight unseen. Product Owner: *"I dont know what
#           these boxes are"*, and *"can you show me the screen where I can
#           clearly wsee how actual template look like"*.
#           Screens: S8 (Settings → Configure → Templates → Standard bill)
# Rules:    BR-BIL-026 (a choice affects FUTURE bills only; an issued bill
#           renders from its own pin forever) · BR-SHL-020 (an absent fact is
#           NAMED, never faked) · BR-TEN-003 / HR-1 (cross-tenant reads as
#           absent) · CLAUDE.md hard-won law 5 (one artefact, derived on demand)
# ───────────────────────────────────────────────────────
"""`GET /bill-templates/layouts/{key}/preview.pdf` — the five layouts, SEEN.

**WHAT THIS FILE IS ACTUALLY GUARDING, AND WHY EACH CASE IS NEGATIVE.**
A preview route is easy to make green and hard to make honest. The plausible
wrong versions each pass a naive test:

  · one that renders a MADE-UP bill — green, and it puts a fictional customer
    and a fictional amount on the one screen whose entire job is to show what a
    real page looks like;
  · one that answers the same bytes for every key — green on "200 and a PDF",
    and it makes the chooser a lie, which is the defect one layer down from the
    one being fixed;
  · one that re-papers the bill it borrows — green on the preview, and it
    breaks BR-BIL-026, which is the rule that made this route necessary in the
    first place.

So: the five keys must produce five DIFFERENT documents from ONE bill, the bill
must be unchanged afterwards (its own render byte-identical), and a tenant with
no issued bill must get a SENTENCE rather than an empty frame.
"""

import pytest

from apps.billing import documents as billing_documents
from apps.billing import layout_preview_api, models, templates_api, templates_service
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call
from tests.test_us_bil_surface_apis import TODAY, _a_bill_pinned_to

pytestmark = pytest.mark.django_db


def test_def_bil_4458__the_route_is_mounted_and_is_not_shadowed_by_the_chooser(brazos):
    """The include exists, and the plural segment does its job.

    ⚠ **THE SECOND HALF IS THE ONE WORTH HAVING.** `bill-templates/layout` (the
    POST that CHOOSES) is all-static; a `<str:…>` directly under
    `bill-templates/` would have swallowed it, and Django resolves by URL and
    not by method, so the collision would have been silent and would have
    broken the write rather than the read.
    """
    from django.urls import resolve

    preview = resolve(
        f"/api/{brazos.subdomain}/bill-templates/layouts/compact-letter-v1/preview.pdf"
    )
    assert preview.func.cls.__module__ == "apps.billing.layout_preview_api"
    assert preview.kwargs == {"layout_key": "compact-letter-v1"}
    chooser = resolve(f"/api/{brazos.subdomain}/bill-templates/layout")
    assert chooser.func.cls.__module__ == "apps.billing.templates_api"


def test_def_bil_4458__five_keys_draw_ONE_real_bill_as_five_DIFFERENT_pages(brazos, dana):
    """The whole point of a chooser: the options differ, and on a REAL bill.

    Both halves are asserted because either one alone is satisfied by a wrong
    implementation — five identical pages would pass "it is a real bill", and
    five different fictions would pass "they differ".
    """
    with tenant_ctx(brazos):
        seeded = templates_service.seed_platform_default(on_date=TODAY)
        bill = _a_bill_pinned_to(brazos, dana, seeded["template_id"], seeded["version_no"])
        pages = {}
        for spec in billing_documents.LAYOUT_SPECS:
            data, content_type, name = layout_preview_api.render_layout_sample(spec.key)
            assert content_type == "application/pdf"
            assert data.startswith(b"%PDF"), f"{spec.key} did not answer a PDF"
            assert name == f"{spec.key}-sample"
            pages[spec.key] = data
    assert len(set(pages.values())) == 5, (
        "two platform layouts drew one bill to the same PAGE, so the chooser is "
        "offering names for one document. That is the defect one layer down from "
        "the one this route fixes."
    )
    # …and it is THIS TENANT'S OWN BILL, not an invention. The bill number is
    # on the page, and no fixture anywhere would have put it there by accident.
    assert bill.invoice_no is not None
    # DEF-BIL-10546 — the preview is the TAGGED page (compressed, glyph-coded),
    # so the number is read back through the page's own text layer.
    from core import tagged_pdf

    assert bill.invoice_no in tagged_pdf.text_of(pages["standard-letter-v1"])


def test_def_bil_4458__previewing_changes_NOTHING_about_the_bill_it_borrows(brazos, dana):
    """BR-BIL-026, from the other direction.

    The route renders an issued bill under a layout it is NOT pinned to. That is
    exactly the act the rule forbids doing to the RECORD, so this asserts the
    record is untouched: no new version, no moved pin, and the bill's own
    document byte-identical before and after.
    """
    with tenant_ctx(brazos):
        seeded = templates_service.seed_platform_default(on_date=TODAY)
        bill = _a_bill_pinned_to(brazos, dana, seeded["template_id"], seeded["version_no"])
        before = billing_documents.render_invoice(bill)
        versions_before = models.Invoice.objects.filter(pk=bill.pk).values_list(
            "template_id", "template_version"
        )[0]

        for spec in billing_documents.LAYOUT_SPECS:
            layout_preview_api.render_layout_sample(spec.key)

        after = billing_documents.render_invoice(bill)
        versions_after = models.Invoice.objects.filter(pk=bill.pk).values_list(
            "template_id", "template_version"
        )[0]
    assert versions_after == versions_before
    assert after.layout_source == before.layout_source == "platform-layout-standard-letter-v1"
    assert after.pdf == before.pdf
    assert after.body == before.body


def test_def_bil_4458__a_utility_that_has_never_billed_gets_a_SENTENCE(brazos, dana):
    """BR-SHL-020 — the honest refusal, and the reason it is not an empty frame.

    A tenant with no issued bill has no document to borrow. Inventing one would
    put a made-up customer on the screen whose job is to show what is real, and
    drawing a blank grey box would assert *"this layout prints an empty page"* —
    a different and alarming claim about a page a customer receives.
    """
    with tenant_ctx(brazos):
        templates_service.seed_platform_default(on_date=TODAY)
        assert layout_preview_api.sample_invoice() is None, (
            "this case needs a tenant that has issued nothing; a fixture that issues "
            "a bill silently turns it into a different test"
        )
        with pytest.raises(Exception) as refused:
            layout_preview_api.render_layout_sample("standard-letter-v1")
        said = str(refused.value)
        assert "has not issued a bill yet" in said
        # …and the SAME sentence reaches the screen through the library read, so
        # the card can say it without asking five times and getting five frames
        # that each fail on their own.
        library = api_call(
            templates_api.bill_templates,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
        ).data
        assert all(row["preview_unavailable"] is not None for row in library["layouts"])
        assert all(
            "has not issued a bill yet" in row["preview_unavailable"]
            for row in library["layouts"]
        )


def test_def_bil_4458__the_library_says_WHERE_to_see_each_layout(brazos, dana):
    """`preview_url` per layout — the wiring, asserted rather than assumed.

    ⚠ **HARD-WON LAW 2: BUILT IS NOT WIRED.** A route that resolves and a screen
    that draws a frame are two facts, and the thing between them is this field.
    A `preview_url` the screen never receives is a route no human can reach.
    """
    with tenant_ctx(brazos):
        seeded = templates_service.seed_platform_default(on_date=TODAY)
        _a_bill_pinned_to(brazos, dana, seeded["template_id"], seeded["version_no"])
        library = api_call(
            templates_api.bill_templates,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
        ).data
    for row in library["layouts"]:
        assert row["preview_unavailable"] is None
        assert row["preview_url"] == f"/bill-templates/layouts/{row['key']}/preview.pdf"


def test_def_bil_4458__an_unpublished_key_is_refused_by_name(brazos, dana):
    """A key the platform does not publish never reaches a renderer.

    The same narrowing `choose_layout` already applies to the WRITE, applied to
    the READ: nothing a caller types can select a page the platform did not
    write (`templates_api`'s own header records why that matters).
    """
    with tenant_ctx(brazos):
        seeded = templates_service.seed_platform_default(on_date=TODAY)
        _a_bill_pinned_to(brazos, dana, seeded["template_id"], seeded["version_no"])
        with pytest.raises(Exception) as refused:
            layout_preview_api.render_layout_sample("../../etc/passwd")
        assert "not one of the platform's printed-bill layouts" in str(refused.value)


def test_def_bil_4458__the_route_answers_a_pdf_over_the_wired_stack(brazos, dana):
    """Over HTTP, with the header a browser frame actually needs.

    `Content-Disposition: inline` is not decoration: as an attachment the frame
    downloads instead of rendering, and the screen shows nothing at all with
    every DOM assertion still passing.
    """
    with tenant_ctx(brazos):
        seeded = templates_service.seed_platform_default(on_date=TODAY)
        _a_bill_pinned_to(brazos, dana, seeded["template_id"], seeded["version_no"])
        response = api_call(
            layout_preview_api.layout_preview_pdf,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            layout_key="letterhead-letter-v1",
        )
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"] == 'inline; filename="letterhead-letter-v1-sample.pdf"'
    assert bytes(response.content).startswith(b"%PDF")

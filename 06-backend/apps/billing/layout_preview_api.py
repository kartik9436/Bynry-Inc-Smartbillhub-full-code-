# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-4458 (2026-09-07) — a System Admin chooses the page every
#           customer receives sight unseen. The Product Owner, looking at the
#           running screen: *"I see some boxes - standard, compact, amount due
#           first, no remitance stub pre-printed leterhead - it doe snot match -
#           I dont know what these boxes are and why so much content below
#           them"*, and, on the template screens generally, *"can you show me
#           the screen where I can clearly wsee how actual template look like"*.
#           Screens: S8 (Settings → Configure → Templates → Standard bill)
# Rules:    BR-BIL-026 (a choice affects FUTURE bills only; an issued bill
#           renders from its own pin forever) · BR-BIL-036 (the printed page is
#           the floor) · BR-SHL-020 (an absent fact is NAMED, never faked) ·
#           BR-TEN-043 (no wall clock) · CLAUDE.md hard-won law 5 (ONE generated
#           artefact, derived on demand, never committed)
# Impacts:  apps/billing/templates_api.py (`preview_url` per layout) ·
#           config/urls.py (the include) · 07-frontend BillLayoutTab
# ───────────────────────────────────────────────────────
"""`GET /bill-templates/layouts/{key}/preview.pdf` — SEE a layout before you
choose it.

════════════════════════════════════════════════════════════════════════════
WHY THIS ROUTE HAD TO EXIST, AND WHY NO EXISTING ONE COULD ANSWER
════════════════════════════════════════════════════════════════════════════
The chooser offers five layouts. Until this file it offered them as five
paragraphs of prose and a button — *"Compact — description and amount only, no
per-service band"* — which is a good sentence and is not a picture. The person
reading it is deciding what every customer of the utility receives in the post.

The obvious answer, *"render one through the bill document route"*, does not
work and the reason is a rule rather than an oversight. `GET /invoices/{id}/
document.pdf` renders an invoice through **its own pin**: `documents._layout_for`
reads the bill's `bill_template_versions.layout_key` and BR-BIL-026 makes that
pin permanent, so the only layout that route can ever produce is the one the
tenant is already on. Asking it for the other four would mean re-papering a bill,
which is precisely what the rule forbids.

So this route renders a SAMPLE — a real issued bill of this tenant's, drawn
with a layout it is not pinned to — and it is deliberately a **read that writes
nothing**: no version, no pin, no audit row, no stored document. Nothing about
the bill it borrows changes, and the bytes are thrown away after the response.

════════════════════════════════════════════════════════════════════════════
HOW IT AVOIDS BEING A SECOND RENDERER (hard-won law 5)
════════════════════════════════════════════════════════════════════════════
It does not re-derive the document. `documents.render_invoice` already returns
every part of the mapping it built — masthead, meta, services, groups, summary,
remarks, usage, footer, stub — on `RenderedDocument`, so this file asks the real
renderer for the real bill and then hands **that same mapping** to a different
`Layout`'s serialiser. One structure, one set of figures, two serialisations;
`documents.py` is not modified and is not copied.

That is what makes the preview honest: what a person sees here is what
`documents.py` will print, because it IS `documents.py` printing it. A drawing
assembled here from the payload would be a second renderer that agrees with the
first until the day it does not — with a customer's bill in it.

════════════════════════════════════════════════════════════════════════════
WHEN IT CANNOT ANSWER, IT SAYS SO (BR-SHL-020)
════════════════════════════════════════════════════════════════════════════
Three refusals, each a sentence a person can act on rather than a blank frame:

  · a key the platform does not publish → `layout_or_refuse`'s own sentence;
  · a key with no renderer (`renders: false`) → named, because the chooser
    already draws that option disabled and the preview must agree with it;
  · **no issued bill to borrow** → the honest one. A utility that has not billed
    yet has no document of its own, and inventing a fictional bill here would
    put a made-up customer and a made-up amount on a screen whose entire job is
    to show what is real. The screen says the layout cannot be previewed until
    the first bill run, which is a fact and is fixable by running one.

`urlpatterns` is exported for inclusion by config/urls.py.
"""

from typing import Any

from django.http import HttpResponse
from django.urls import path
from rest_framework.decorators import api_view, permission_classes

from apps.billing import documents, models, templates_service, tenancy_seam
from apps.billing.exceptions import BillingRuleError
from core import errors
from core.permissions import AnyTenantRole
from core.tenancy import require_tenant

#: The invoice statuses whose document is a real thing a customer received. A
#: DRAFT has no pin (BR-BIL-026) and `render_invoice` refuses it by name, so
#: borrowing one would turn a preview into an error a person cannot act on.
SAMPLE_STATUSES: tuple[str, ...] = ("issued", "corrected")


def _refusal(broken: BillingRuleError) -> errors.BizError:
    """A renderer refusal, in the renderer's own words."""
    return errors.ValidationError(
        errors.VAL_INVALID,
        message_key="billing.templates.layout_preview_refused",
        message=str(broken),
    )


def sample_invoice() -> Any:
    """The bill this preview borrows: the tenant's most recently ISSUED one.

    ⚠ **DETERMINISTIC, AND THAT IS NOT DECORATION.** Two people comparing two
    layouts side by side must be looking at the same bill, or the difference
    they see is the customer and not the layout. `-issued_at, -pk` is a total
    order (`issued_at` can tie inside one bill run; the pk breaks it), so every
    request for every layout picks the same row until the next bill run.

    ⚠ **NO CLOCK.** It orders by a stored column and filters on status; nothing
    here asks what today is (BR-TEN-043, and G6 greps this module for it).

    Returns `None` when the tenant has never issued a bill. That is a state the
    screen must be able to NAME, not an error — see this module's header.
    """
    return (
        models.Invoice.objects.filter(status__in=SAMPLE_STATUSES)
        .order_by("-issued_at", "-pk")
        .first()
    )


def render_layout_sample(layout_key: str) -> tuple[bytes, str, str]:
    """One layout, drawn on a real bill. Returns `(pdf, content_type, name)`.

    Raises `BillingRuleError` for everything a person can act on: an unpublished
    key, a key with no renderer, no bill to borrow, a bill whose own render is
    refused.
    """
    layout = templates_service.layout_or_refuse(layout_key, template_type="bill")
    if not layout.renders:
        raise BillingRuleError(
            f"{layout.label!r} is listed in the platform's library but nothing renders it, "
            "so there is no page to show. The chooser draws it disabled for the same reason."
        )
    invoice = sample_invoice()
    if invoice is None:
        raise BillingRuleError(
            "this utility has not issued a bill yet, so there is no real document to draw "
            f"{layout.label!r} on. Run a bill run and the five layouts can each be seen on "
            "a page of your own; nothing here invents a customer or an amount."
        )

    # ⚠ THE REAL RENDER FIRST, THROUGH THE REAL PATH. Everything below is a
    # RE-SERIALISATION of the mapping this call already built — see the header.
    rendered = documents.render_invoice(invoice)
    document = {
        "invoice_no": rendered.invoice_no,
        "template_version": rendered.template_version,
        "payload_version": rendered.payload_version,
        # ⚠ The SOURCE says this page was drawn for a chooser, not pinned. It
        # travels into the HTML as `data-layout-source`, so a page saved out of
        # this route can never be mistaken for the document a customer received.
        "layout_source": f"layout-preview:{layout.key}",
        "masthead": rendered.masthead,
        "meta": rendered.meta,
        "services": rendered.services,
        "groups": rendered.groups,
        "summary": rendered.summary,
        "remarks": rendered.remarks,
        "usage": rendered.usage,
        "footer": rendered.footer,
        "stub": rendered.stub,
        # CR-172-BRC10 — the CURRENT logo, not the borrowed bill's stamp: this
        # page shows what the NEXT bill on this layout will look like, and the
        # next bill is stamped with today's logo. A real bill keeps its own.
        "logo": documents.logo_for(tenancy_seam.bill_logo()),
    }
    serialiser = documents.LAYOUTS_BY_KEY[layout.key]
    try:
        # DEF-BIL-10546 — the TAGGED page, because that is what the NEXT bill on
        # this layout will be (every bill issued from 2026-10-23 on).
        page = serialiser.tagged_pdf(document)
    except BillingRuleError:
        raise
    except Exception as broken:  # noqa: BLE001 — one named break, never a 500
        raise BillingRuleError(
            f"{layout.label!r} could not draw bill {rendered.invoice_no or rendered.invoice_id} "
            f"({type(broken).__name__}: {broken}). Nothing about that bill changed and it still "
            "prints on its own layout; only this preview is unavailable."
        ) from broken
    name = f"{layout.key}-sample"
    return page.data, "application/pdf", name


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: the same read as the chooser itself
def layout_preview_pdf(request: Any, layout_key: str) -> Any:
    """A layout, drawn on this tenant's most recent bill, as `application/pdf`.

    INLINE, because the whole point is to look at it: the frame on S8 shows the
    page and the browser's own viewer carries print and save, which is the same
    posture `invoice_document_pdf` takes for a real bill.

    ⚠ **IT WRITES NOTHING.** No version, no pin, no stored document, no audit
    row — CLAUDE.md rule 7 asks for an audit row on every MONEY ACTION and this
    moves no money and changes no record. Choosing a layout is the money-shaped
    act and `choose_bill_layout` audits it.
    """
    require_tenant(request)
    try:
        page, content_type, name = render_layout_sample(layout_key)
    except BillingRuleError as broken:
        raise _refusal(broken) from broken
    response = HttpResponse(page, content_type=content_type)
    response["Content-Disposition"] = f'inline; filename="{name}.pdf"'
    # CR-172-BRC10 — the preview draws the CURRENT logo, so the same address
    # changes when the logo is replaced; a browser must not draw its old copy.
    response["Cache-Control"] = "no-store"
    return response


urlpatterns = [
    # ⚠ ORDER AND SHAPE WERE CHECKED, NOT ASSUMED. The sibling `bill-templates/
    # layout` (the POST that CHOOSES) is all-static and singular; this is
    # `layouts/…` and four segments deep, so neither can swallow the other. A
    # `<str:layout_key>` under `bill-templates/` on its own WOULD have swallowed
    # `layout`, which is why the plural segment is there.
    path("bill-templates/layouts/<str:layout_key>/preview.pdf", layout_preview_pdf),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-BIL-4458 (12-governance/10-defect-log.csv) · US-BIL-021 (the
#         chooser this serves) · US-BIL-022 (the pin it must not touch) ·
#         apps/billing/documents.py LAYOUT_SPECS · 07-billing/02-business-rules.md
#         BR-BIL-026 / BR-BIL-036
# generated: 2026-09-07 by the SET-10/bill-layout lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_def_bil_4458_layout_preview.py could not
#        resolve the route through the root URLconf before this file was
#        included, and the five layouts were shown to produce five DIFFERENT
#        PDFs from ONE bill only after that.
# exceptions: E3 `documents.py` is NOT modified — it is on human_owned.txt and
#         its `RenderedDocument` already publishes every part of the mapping, so
#         the re-serialisation needs no new seam there · E3 the preview borrows a
#         REAL bill and never invents one: a fictional customer on the screen
#         whose job is to show what is real is the defect one layer down · E3 no
#         write of any kind, so no audit row (rule 7 is about money actions and
#         `choose_bill_layout` is the one here)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

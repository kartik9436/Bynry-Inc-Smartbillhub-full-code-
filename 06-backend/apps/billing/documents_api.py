# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-022 (pinning at issue + reprint renders the pinned version
#           forever — the READ half: `GET /invoices/{id}/document`) ·
#           US-BIL-026 (S30 bill detail's `document_url`, which was served null
#           because nothing was mounted to point it at)
#           Screens: S30 (bill detail → View the bill as sent)
# Rules:    BR-BIL-026 (the pinned template version renders the document — the
#           SERVER renders it, never the browser) · BR-BIL-030 (the bill is
#           LOCKED at issue: the document is rendered from the frozen instance,
#           never from live joins) · BR-CUS-040 (a reprint re-renders the
#           ISSUED document, never recomputes) · BR-BIL-036 (print is the floor,
#           so the printable page is served as well as the structure) ·
#           BR-BIL-033 (a bill that cannot become a document is refused at
#           issue — this route reports that refusal instead of 500ing) ·
#           BR-TEN-003 / HR-1 (a cross-tenant id reads as absent) ·
#           BR-SHL-025 / BR-IDN-009 (server-enforced RBAC) · BR-SHL-020 (a
#           refusal a human can act on)
# Tests:    06-backend/tests/test_us_bil_surface_apis.py
# Impacts:  config/urls.py (the include) · apps/billing/selectors.invoice_detail
#           (`document_url` stops being null) · 07-frontend BillDetailPage
# ───────────────────────────────────────────────────────
"""`GET /invoices/{id}/document` — the bill a person can actually open.

WHY THIS FILE EXISTS. `apps/billing/documents.py` is 1,800 lines that render a
bill twice — as a structure with an HTML serialisation and as a printable US
Letter PDF written with the standard library — and `issue.py` calls it on every
bill to satisfy BR-BIL-033 **and throws the result away**. Its own
`DOCUMENT_UNAVAILABLE` says so in as many words: *"`GET /invoices/{id}/document`
is still unmounted, so no human can open one either (hard-won law 2)."* That
sentence has been true since the renderer landed. This module is the mounting.

⚠ IT NOW SERVES THE BILL THAT WAS ISSUED, NOT A REBUILD OF IT (CR-049 task 4,
2026-08-30, closing DEF-2553)
════════════════════════════════════════════════════════════════════════════
This module's first paragraph below said it *"does not store the document"* and
that *"a re-render is byte-stable only while the layout code is"*. Both were
true, and the second describes the defect exactly: `BR-NOT-027` (PO 2026-08-30)
makes a legal document frozen AS THE DOCUMENT, and a bill is the most important
one this product makes.

So every response now carries a `provenance`, and it is **one of exactly two
values**:

  * `original` — an artefact was kept at issue. `original_html` is those bytes,
    hash-verified on this read, and `/document.pdf` streams the kept page.
  * `re_rendered_from_data_not_the_original` — no copy was kept, which is every
    bill issued before `v2.88.0`. `frozen_document` and `original_html` are
    **null**, and `message_key` names the sentence the screen must draw.

⚠ **THE STRUCTURED BANDS ARE STILL A RE-RENDER AND ARE HONEST ABOUT IT.** They
are how the S30 page draws a searchable, escaped, accessible view of the bill,
and they always were. What changes is that they are no longer the ANSWER to
*"show me the bill as sent"* — the frozen HTML is, and the page draws that. Every
figure in the bands is nonetheless the frozen one (`BR-BIL-030`), which is why
they can sit beside the original without contradicting it.

⚠ **A TAMPERED DOCUMENT REFUSES; IT NEVER DEGRADES INTO "re-rendered".** Those
are different facts with different remedies — one means no copy was kept, the
other means one was kept and its bytes are now wrong — and collapsing them would
hide a corrupted seven-year record behind a reassuring caption. The same
judgement `notifications/reprint_api.py` records.

TWO THINGS IT DELIBERATELY DOES NOT DO
════════════════════════════════════════════════════════════════════════════
1. **It does not render on behalf of a frozen bill.** When an original exists it
   is fetched and served; the re-render is what fills the structured bands and
   what a bill with no original falls back to, labelled.

2. **It does not re-price anything.** `render_invoice` reads the invoice row and
   its own `invoice_lines` and nothing else. A bill issued in July renders July's
   name, July's address and July's numbers in 2031, because the payload was
   frozen at issue (BR-BIL-030). Nothing here reaches for a customer record.

3. **It serves no write verb.** Correcting a document is a class-D correction
   case (US-BIL-031, `corrections_api.py`), which writes a NEW instance and
   leaves the original. There is no PUT here and there must never be one.

WHAT A DRAFT ANSWERS, AND WHY IT IS NOT A 404
════════════════════════════════════════════════════════════════════════════
A draft has no pin (BR-BIL-026 stamps it at issue), so there is nothing to
render and `render_invoice` refuses. That refusal is not "this bill does not
exist" — the clerk is looking at the bill — so it comes back as a 422 carrying
the renderer's own sentence rather than as the HR-1 not-found. The 404 is
reserved for what HR-1 reserves it for: an unknown id, a malformed id and
another tenant's id, which are one byte-identical answer.

TWO REPRESENTATIONS, ONE PIN
════════════════════════════════════════════════════════════════════════════
`/document` answers the STRUCTURE plus its HTML, and `/document.pdf` answers the
printable page. Both come out of ONE `render_invoice` call in the same request,
because `Layout` carries the pair and selecting them separately is how an HTML
view and a printed page start disagreeing about what a bill says — with the
customer holding the page.

`urlpatterns` is exported for inclusion by config/urls.py.
"""

from typing import Any

from django.http import HttpResponse
from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.billing import documents, frozen_bill, selectors
from apps.billing.exceptions import BillingRuleError
from apps.tenancy import document_storage, document_store
from core import errors
from core.permissions import AnyTenantRole
from core.tenancy import require_tenant

#: The i18n keys this file's refusals carry. Named once so G18 can read the
#: catalogue and the code against each other in one grep; a key with no
#: catalogue entry renders to a clerk as a raw dotted string.
KEY_HASH_MISMATCH = "billing.document.hashMismatch"
KEY_BYTES_MISSING = "billing.document.bytesMissing"

#: The header a browser-level client reads without parsing a body. It exists
#: because `/document.pdf` answers `application/pdf` and cannot carry a caption:
#: a page has nowhere to say *"this is a rebuild"*, so the response says it.
PROVENANCE_HEADER = "X-Document-Provenance"


def _refusal(broken: BillingRuleError) -> errors.BizError:
    """The renderer's own sentence, as the one catalog exception G9 allows.

    Identical in shape to `api._as_catalog_refusal` and deliberately not
    imported from it: that helper defaults its `br_ref` to a RUN rule, and a
    document that cannot be rendered is not a run problem. The sentence travels
    in `params.detail` because it is written for a clerk (BR-SHL-020) — "this
    bill is still a draft, so no template version has been pinned to it yet" is
    something a person can act on and `BIZ-COMPLETENESS` on its own is not.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(broken, "br_ref", None) or "BR-BIL-026",
        message_key="billing.document.refused",
        params={"detail": str(broken)},
    )


def _layout_dict(spec: Any) -> dict[str, Any]:
    """The pinned layout's switches, as the viewer branches on them (DEF-2826).

    ⚠ **A DOCUMENT WITHOUT A SPEC FALLS BACK TO THE DEFAULT ONE, NAMED, AND
    NEVER TO AN EMPTY DICT.** Every switch is a boolean the page reads as
    *"draw this band"*, so an absent spec read as `{}` would suppress the
    masthead, the services band, the detail columns and the stub all at once —
    a blank bill presented as the customer's. The default layout is
    `standard-letter-v1` and it is what every pre-library bill renders on, so
    it is the honest stand-in as well as the safe one.
    """
    resolved = spec if spec is not None else documents.SPECS_BY_KEY[documents.DEFAULT_LAYOUT_KEY]
    return {
        "key": resolved.key,
        "masthead": resolved.masthead,
        "services_band": resolved.services_band,
        "detail_columns": resolved.detail_columns,
        "summary_first": resolved.summary_first,
        "stub": resolved.stub,
        "reserve_rows": resolved.reserve_rows,
    }


def _absent_dict(entry: documents.AbsentField | None) -> dict[str, Any] | None:
    if entry is None:
        return None
    return {"field": entry.field, "why": entry.detail, "br_ref": entry.br_ref}


def _field_dicts(fields: Any) -> list[dict[str, Any]]:
    """`DocumentField` rows as JSON, each carrying its OWN absence if it has one.

    Values are already display-formatted STRINGS at the precision the payload
    froze them at — CLAUDE.md rule 2: nothing here parses, sums or re-rounds a
    money figure. A field the snapshot did not carry travels with the reason it
    is missing attached to it, so the viewer can badge the exact line rather
    than printing the renderer's absence mark and leaving the clerk to guess
    which of twelve fields it belonged to.
    """
    return [
        {"label": field.label, "value": field.value, "absent": _absent_dict(field.absent)}
        for field in fields
    ]


def _refuse_unreadable(problem: Exception, reference: Any) -> errors.BizError:
    """A kept bill that will not read back is REPORTED, never softened.

    ⚠ **IT MUST NOT DEGRADE INTO "re-rendered from data".** That sentence is the
    honest answer when NO copy was kept. Here a copy WAS kept and its bytes are
    now wrong — a different fact, with a different remedy, and one somebody has to
    be told rather than have smoothed over by a reassuring caption (hard-won law
    1: a guarantee is worth nothing if its failure looks like a normal state).
    """
    if isinstance(problem, document_storage.ContentHashMismatch):
        return errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-NOT-027",
            message_key=KEY_HASH_MISMATCH,
            params={"document_id": str(reference.id), "display_name": reference.display_name},
        )
    return errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-NOT-027",
        message_key=KEY_BYTES_MISSING,
        params={"document_id": str(reference.id), "display_name": reference.display_name},
    )


def _verified(reference: Any) -> bytes:
    """The kept bytes, hash-checked on this read, or the refusal that says why.

    ⚠ **THE HASH IS RE-COMPUTED HERE AND NOT TAKEN ON TRUST** (`CR-049` step
    5d(e) decision 7). A pre-signed link is a direct client-to-cloud read, so our
    code is not in that path and nothing hashes anything; serving only a link
    would have retired the one check that catches a document quietly replaced
    years later, while every test still passed because the link works.
    """
    try:
        return document_store.fetch(reference.id)
    except (
        document_storage.ContentHashMismatch,
        document_storage.DocumentStorageError,
        document_store.DocumentStoreError,
    ) as problem:
        raise _refuse_unreadable(problem, reference) from problem


def _document_reference(reference: Any) -> dict[str, Any] | None:
    """One kept artefact as a screen receives it — **never a storage key**.

    A key is how tenancy finds bytes; handing one out would let a caller ask for
    a key it composed, which is the one thing `document_storage` says must never
    happen (`CR-049` step 5d(e) decision 4). A caller wanting the bytes has them
    inline; a caller wanting to give somebody a link gets a four-hour one minted
    from the row this module already resolved.
    """
    if reference is None:
        return None
    return {
        "id": str(reference.id),
        "kind": reference.kind,
        "display_name": reference.display_name,
        "content_type": reference.content_type,
        "content_hash": reference.content_hash,
        "byte_length": reference.byte_length,
        "stored_at": reference.stored_at.isoformat(),
        "storage_backend": reference.storage_backend,
    }


def _provenance_dict(reproduction: Any, original_html: str | None) -> dict[str, Any]:
    """The two states, on every response, as values a screen must branch on.

    There is no third state that means *"probably"*. A screen that draws the
    re-render without drawing `message_key`'s sentence has produced the defect
    `BR-NOT-027` was written for — a fresh document presented as the bill.
    """
    return {
        "provenance": reproduction.provenance,
        "message_key": reproduction.i18n_key,
        "provenance_detail": reproduction.detail,
        "unavailable_reason": reproduction.unavailable_reason,
        "original_html": original_html,
        "frozen_document": _document_reference(reproduction.html),
        "frozen_page": _document_reference(reproduction.pdf),
    }


def _rendered_dict(rendered: documents.RenderedDocument) -> dict[str, Any]:
    """The document, as the S30 viewer reads it.

    FOUR TUPLES TRAVEL, AND KEEPING THEM APART IS THE POINT (the renderer's own
    docstring argues it): `absent` is what this bill's snapshot did not carry,
    `unavailable` is what the build cannot do at all, `pdf_unrepresentable` is a
    character the PAGE cannot spell, and `problems` is the report addressed to
    whoever ran the bill run. A screen that merged them would tell a clerk that
    a missing total due and an un-embeddable font are the same kind of thing.
    """
    return {
        "invoice_id": rendered.invoice_id,
        "invoice_no": rendered.invoice_no,
        "template_id": rendered.template_id,
        "template_version": rendered.template_version,
        "payload_version": rendered.payload_version,
        "layout_source": rendered.layout_source,
        # DEF-2826 — WHAT that layout does, beside WHICH layout it is. The
        # viewer had the name and drew every band regardless, so a bill pinned
        # to `compact-letter-v1` was announced compact and drawn standard. The
        # switches are the layout's OWN declaration (`documents.LayoutSpec`),
        # served rather than re-derived on the client: a screen that decided for
        # itself which bands a layout suppresses is a second copy of the rule
        # and would drift from the page the customer actually holds.
        "layout": _layout_dict(rendered.layout),
        "currency": rendered.currency,
        "content_type": rendered.content_type,
        "body": rendered.body,
        "pdf_content_type": rendered.pdf_content_type,
        "pdf_page_count": rendered.pdf_page_count,
        "pdf_url": f"/invoices/{rendered.invoice_id}/document.pdf",
        "masthead": _field_dicts(rendered.masthead),
        "meta": _field_dicts(rendered.meta),
        "services": _field_dicts(rendered.services),
        "groups": [
            {
                "heading": group.heading,
                "absent": _absent_dict(group.absent),
                "lines": [
                    {
                        "description": line.description,
                        "quantity": line.quantity,
                        "unit_price": line.unit_price,
                        "amount": line.amount,
                    }
                    for line in group.lines
                ],
            }
            for group in rendered.groups
        ],
        "summary": _field_dicts(rendered.summary),
        # US-BIL-028 — the tenant's own custom fields, as the ONE remark/note
        # section the PO ruled on 2026-08-12. `[]` when the tenant defined none,
        # and the viewer omits the section rather than drawing an empty box:
        # an empty Remarks heading invites the question of what belongs in it.
        "remarks": _field_dicts(rendered.remarks),
        # A19 §1.7 — CR-052 task 9, closing DEF-2714. The block is FROZEN on the
        # bill (`bill_payload.usage_history`, stamped at issue by task 8) and
        # this is the only place it is served, so the viewer draws the twelve
        # months the customer was sent rather than the twelve months that are
        # true today — the live join BR-BIL-030 forbids and the reason the
        # frontend half could not be built before this line existed.
        #
        # `quantity` travels beside `quantity_display` because a bar's HEIGHT is
        # computed from it; it is a quantity, not money, and it carries its unit
        # (rule 3). No identifier is served: the series is named by the service
        # NAME (B14 rule 31).
        "usage": [
            {
                "heading": series.heading,
                "unit": series.unit,
                "months_present": series.months_present,
                "absent": _absent_dict(series.absent),
                "months": [
                    {
                        "label": month.label,
                        "quantity": month.quantity,
                        "quantity_display": month.quantity_display,
                        "unit": month.unit,
                        "absent": month.absent,
                        "estimated": month.estimated,
                    }
                    for month in series.months
                ],
            }
            for series in rendered.usage
        ],
        "footer": _field_dicts(rendered.footer),
        "stub": _field_dicts(rendered.stub),
        "absent": [_absent_dict(entry) for entry in rendered.absent],
        "pdf_unrepresentable": [_absent_dict(entry) for entry in rendered.pdf_unrepresentable],
        "problems": [
            {
                "code": problem.code,
                "invoice_id": problem.invoice_id,
                "invoice_no": problem.invoice_no,
                "br_ref": problem.br_ref,
                "detail": problem.detail,
            }
            for problem in rendered.problems
        ],
        "unavailable": [dict(entry) for entry in rendered.unavailable],
    }


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Reads & Billing runs — Executive View
def invoice_document(request: Any, invoice_id: str) -> Response:
    """The bill as it was sent — structure, HTML and the link to its page.

    READ ONLY, like every other route on an invoice path (BR-BIL-004 / HR-4).
    Neither half writes anything: the kept bytes are read and hashed, and the
    structure is opened from the frozen payload and the pinned version, so a
    clerk refreshing this screen cannot change a customer's record.

    ⚠ **THE ORIGINAL IS RESOLVED FIRST, BEFORE ANYTHING IS RENDERED.** A bill
    with a kept copy has that copy served; the render only fills the structured
    bands beside it. Doing it the other way round — render, then decide — is how
    a route ends up quietly serving the rebuild when the fetch is slow or
    refuses, which is `DEF-2553` again with a stored document in the room.
    """
    require_tenant(request)
    invoice = selectors.invoice_or_404(invoice_id)
    reproduction = frozen_bill.reproduce(invoice)
    original_html = (
        _verified(reproduction.html).decode("utf-8", errors="replace")
        if reproduction.is_original
        else None
    )
    try:
        rendered = documents.render_invoice(invoice)
    except BillingRuleError as broken:
        raise _refusal(broken) from broken
    payload = _rendered_dict(rendered)
    payload.update(_provenance_dict(reproduction, original_html))
    return Response(payload)


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def invoice_document_pdf(request: Any, invoice_id: str) -> Any:
    """The printable page (BR-BIL-036's floor), as `application/pdf`.

    INLINE, not an attachment: a clerk answering a phone call wants the page on
    screen beside the account, and the browser's own viewer offers the download
    and the print. The filename is still declared so a save keeps the bill
    number rather than a uuid.

    ⚠ **THE KEPT PAGE, WHEN THERE IS ONE (CR-049 task 4).** This docstring used
    to end: *"There is no cached artifact to stream, and pretending otherwise
    would claim a durable document exists."* There is one now, it is streamed,
    and it is hash-verified on the way out. A bill issued before `v2.88.0` has
    none and falls back to the re-render — **which the response SAYS**, in
    `X-Document-Provenance`, because a PDF has nowhere to carry a caption and a
    rebuild handed over as `application/pdf` with nothing marking it is exactly
    what `BR-NOT-027` forbids.
    """
    require_tenant(request)
    invoice = selectors.invoice_or_404(invoice_id)
    reproduction = frozen_bill.reproduce(invoice)
    if reproduction.is_original and reproduction.pdf is not None:
        page = _verified(reproduction.pdf)
        name = invoice.invoice_no or str(invoice.pk)
        response = HttpResponse(page, content_type=reproduction.pdf.content_type)
        response["Content-Disposition"] = f'inline; filename="{name}.pdf"'
        response[PROVENANCE_HEADER] = frozen_bill.PROVENANCE_ORIGINAL
        return response

    try:
        rendered = documents.render_invoice(invoice)
    except BillingRuleError as broken:
        raise _refusal(broken) from broken
    name = rendered.invoice_no or rendered.invoice_id
    response = HttpResponse(rendered.pdf, content_type=rendered.pdf_content_type)
    response["Content-Disposition"] = f'inline; filename="{name}.pdf"'
    response[PROVENANCE_HEADER] = frozen_bill.PROVENANCE_RE_RENDERED
    return response


urlpatterns = [
    # ORDER IS LOAD-BEARING: `document.pdf` is all-static and is declared FIRST
    # so `<str:invoice_id>` in the sibling route can never swallow it. Django
    # matches in order and both patterns are three segments deep.
    path("invoices/<str:invoice_id>/document.pdf", invoice_document_pdf),
    path("invoices/<str:invoice_id>/document", invoice_document),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-022@5397d5f (the same four sources apps/billing/documents.py was authored from — 04-docs/01-spec/19-document-templates.md A19 · 04-docs/05-modules/07-billing/06-epics/EP-BIL-06-templates-delivery.md US-BIL-022 · 07-billing/02-business-rules.md BR-BIL-026/030/033/036 · 04-docs/01-spec/11b-api-audit.md §2.8 — so a change to any of them makes this stamp findable as stale in one grep)
# generated: 2026-08-16 by story-coder (billing SURFACE lane — the route documents.py's own DOCUMENT_UNAVAILABLE named as unmounted)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_us_bil_surface_apis.py could not resolve `/invoices/{id}/document` through the root URLconf before this file was included; the failure is quoted verbatim in the lane report. tsc n/a · pytest✔ · run_gates✔ · golden 33/33✔
# exceptions: E3 the document is RE-RENDERED per request and not streamed from storage — there is no document table and no blob store (documents.DOCUMENT_UNAVAILABLE `document_not_stored`), and that entry rides on every response rather than being smoothed over here · E3 a DRAFT answers 422 with the renderer's own sentence, NOT 404: the bill exists and the clerk is looking at it, so the HR-1 not-found is reserved for an unknown/malformed/cross-tenant id · E3 no write verb of any kind is served on this path — a document correction is a class-D correction CASE (US-BIL-031) and writes a new instance
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

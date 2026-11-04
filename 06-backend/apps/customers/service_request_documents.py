# ── Trace ──────────────────────────────────────────────
# Change:   "A clerk cannot attach a document to a service request." The PO
#           ruled it in, verbatim: *"you will have to reduce the size and save
#           them on cloud container etc"*. The capture screen's step 4 said
#           *"We cannot take a file yet — there is nowhere to store it"*, and
#           that sentence was true until this landed.
# Rules:    BR-SHL-031 (CONFIRMED — "upload guards (PDF/PNG/JPG/CSV allowlist,
#           10MB tenant-config, malware scan pre-acceptance); legal class
#           WRITE-ONCE 7yr; v1 uploads staff-mediated" — its scan clause
#           SUPERSEDED by the PO, 2026-09-22/23, DEF-SHL-6347) · BR-CUS-095 (the
#           closed doc-type vocabulary) · BR-WRK-047 (the product's existing
#           ruling on shrinking an image) · 11b G11 (413 over the cap, 415
#           outside the allowlist) · NFR-33 / NFR-35 · BR-TEN-003 (existence
#           must not leak) · B2 §2 (cross-module writes are forbidden) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 7 (audit) ·
#           hard-won law 14 (a failed statement poisons the whole PostgreSQL
#           transaction)
# Tests:    06-backend/tests/test_service_request_documents.py
# Impacts:  apps/customers/service_request_api.py (POST multipart on
#           /service-requests/{id}/documents, GET …/documents/{docId}/download)
#           · apps/customers/service_request_reads.py (documents_tab serves the
#           two sizes) · 07-frontend step 4 of the capture wizard — NOT built
#           here; that file is owned by another lane.
# ───────────────────────────────────────────────────────
"""Attaching a real file to a service request, and getting it back.

THE ONE THING THIS MODULE DOES NOT DO IS STORE A FILE
──────────────────────────────────────────────────────────────────────────────
Every byte goes to `apps.tenancy.document_store.store()`, which has existed
since `CR-049` task 1 and already does the hard parts: the object store behind a
vendor-neutral seam, the sha256 written and re-checked on the way back out, the
seven-year object lock (⚠ the object LOCK is suspended from 2026-10-02, `CR-160-BRC10`; the row stays write-once),
the write-once trigger, and the RLS-scoped read that is
the **only** way a storage key can ever be learned. Nothing here composes a key,
accepts a key, or touches a bucket — B2 §2's ban on cross-module writes, honoured
by calling the published door rather than by hoping.

This is `apps/customers/account_documents.py` one table across, deliberately.
A second storage path for customer files would be the easy thing to write and
the thing that makes *"which copy is the document"* have two answers.

WHY THE `source_id` IS THE ATTACHMENT ROW AND NOT THE REQUEST
──────────────────────────────────────────────────────────────────────────────
⚠ **THIS IS THE ONE THAT WOULD HAVE SHIPPED BROKEN**, and it has now been the
one that would have shipped broken three times — `tenancy/0040` for a
technician's ninth photograph, `tenancy/0044` for a clerk's second account
document, `tenancy/0045` for this.

`uq_stored_documents_filed` allows ONE artefact per
`(tenant, source_type, source_id, content_type)` where the channel is NULL, and
its reasoning is about RENDERINGS: a bill's PDF and its HTML are two
representations of one document, so a source carrying two artefacts of the same
shape would make *"serve the frozen copy"* a choice.

That is right about a bill and it does not describe a counter. An applicant for
a new connection hands over a driving licence AND a tenancy agreement AND a site
plan — three `application/pdf`s on one request. Had this filed under the REQUEST
the first would work and **the second would be refused by the database**, on the
most ordinary thing a clerk does all day. So the attachment row's own id is the
source, which is trivially unique and honest about what the document is a copy
of: itself.

⚠ **THE CONSTRAINT IS NOT WIDENED.** Widening it would weaken a real guarantee
on `invoices` for every other module.

REDUCE ONCE, ON THE WAY IN, BEFORE THE FILE IS FILED
──────────────────────────────────────────────────────────────────────────────
`core.document_shrink.reduce_on_the_way_in` runs **before** `store()` and never
after. The store exists so a filed document cannot be altered or deleted — it
refuses a backend that cannot promise that — so a reduction running after filing
would be rewriting evidence under a retention lock.

⚠ **AND NOTHING THAT MODULE DOES IS LOSSY.** Read its docstring before changing
this: these are a driving licence, a deed and a site plan, every one of them a
thing a clerk reads a number or a boundary off, and the Accounts blueprint's own
worked example carries a site plan marked `Rejected · unreadable`. Measured on
56 real PNG files the lossless path returns **26.4%** (18,076,547 → 13,306,223
bytes) with every pixel unchanged. The larger saving a downscale would buy is
recorded in the decision log rather than taken.

**Both sizes are kept.** `size` is what is on disk; `original_size` is what the
clerk chose, written only when the two differ. A clerk told a file is 3.1 MB who
finds 400 KB on disk needs the record to say why.

ATTACHING IS NOT VERIFYING, AND THIS MODULE CANNOT DO THE SECOND
──────────────────────────────────────────────────────────────────────────────
Every attachment lands `not_checked` and stays there until a person looks at it.
That is the detail's own `BLOCKING` callout — *"attaching a file is not the same
as verifying it"* — and `verify_document` in `service_request_service.py` is the
only thing that moves it. This module does not import it and must not.

THERE IS NO VIRUS SCAN — PO, 2026-09-22 AND 2026-09-23
──────────────────────────────────────────────────────────────────────────────
PO, verbatim, 2026-09-23: *"please remove virus scan chek user don't wan't it.
we have ask remove it before why you did not remove it?"*. From 2026-09-13 a
scanner ran in middleware in front of this module (`BR-SHL-253`), and on a host
with no scanner daemon it refused every file New Request step 4 sent — *"The
virus scanner is unreachable"* — so nothing ever attached. It is deleted
(`DEF-SHL-6347`). The allowlist and the cap below are the whole upload guard.

⚠ **`not_checked` IS NOT A SCAN STATE AND NEVER WAS.** It is the stored value
for *no reviewer has decided yet*. The PO's 2026-09-22 ruling — *"you will have
only two cases verified or rejected"* — is honoured on screen: every table
prints a document's state through `components/documents/DocumentStateCell`,
which shows `Verified`, `Rejected` with its short reason, or nothing.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.customers import models
from apps.tenancy import document_store
from apps.tenancy.document_models import (
    KIND_SERVICE_REQUEST_DOCUMENT,
    SOURCE_SERVICE_REQUEST_DOCUMENT,
)
from core import audit as core_audit
from core import document_shrink, errors
from core.dbfields import uuid7
from core.tenancy import current_tenant_id

# ═══════════════════════════════════════════════════════════════════════════
# THE GUARDS — `BR-SHL-031`, quoted rather than chosen
# ═══════════════════════════════════════════════════════════════════════════

#: *"10MB tenant-config"*. ⚠ **THE SAME FIGURE AS
#: `account_documents.MAX_UPLOAD_BYTES`, AND IT IS THE SAME RULE RATHER THAN A
#: coincidence** — one signed sentence covers every upload door in this product.
#: The tenant half is not built anywhere; inventing a settings key here would be
#: how two spellings of one option appear.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

#: *"PDF/PNG/JPG/CSV allowlist"*. ⚠ **BOTH SPELLINGS OF A JPEG AND ALL THREE OF
#: A CSV**, because a browser sends `image/jpeg` and some scanners send
#: `image/jpg`, and Excel sends `application/vnd.ms-excel` for a file a person
#: calls a CSV. Refusing a file for the SPELLING of its type would be a 415 a
#: clerk cannot act on. Copied from `account_documents` on purpose: two upload
#: doors in one module disagreeing about what a JPEG is called would be a defect
#: nobody could reproduce.
ALLOWED_CONTENT_TYPES = (
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
)

#: What a clerk sees when a file is refused — the EXTENSIONS, not the media
#: types, because `application/vnd.ms-excel` is not a sentence anybody can act
#: on. B14 rule 33 caps a FACT at six words; this is a parameter in a message,
#: not the message.
ALLOWED_EXTENSIONS = ("PDF", "PNG", "JPG", "CSV")


class UploadRefused(Exception):
    """A **413** or a **415** — a B12 r1 transport row with no catalog code.

    ⚠ **RAISED FROM THE SERVICE AND MAPPED IN THE API, NOT THE OTHER WAY
    ROUND**, exactly as `account_documents.UploadRefused` is. The guard lives in
    ONE place — here — and carries its status out with the refusal, so there is
    no second implementation to keep in step and no path that reaches
    `document_store.store()` unguarded.

    `core.errors.ApiError` cannot carry these: `HTTP_STATUS_BY_CODE` maps a
    catalog code to a status and neither 413 nor 415 has one, so a
    `ValidationError` here would answer **422** to a file that is too large.
    """

    def __init__(self, status: int, message_key: str, *, br_ref: str, **params: Any) -> None:
        self.status = status
        self.message_key = message_key
        self.br_ref = br_ref
        self.params = params
        super().__init__(f"{status} {message_key}")


def _tenant_id() -> Any:
    tenant_id = current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None)


def _request_or_404(request_id: Any) -> Any:
    """The request, under THIS tenant — or the same answer as "never existed".

    ⚠ Resolved BEFORE anything else, on every path. A caller in another utility
    asking about a request it cannot see gets a 404, never a 403: a 403 confirms
    the request exists (`BR-TEN-003`, HR-1 — existence must not leak).
    """
    row = models.ServiceRequest.objects.filter(tenant_id=_tenant_id(), pk=request_id).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _row_or_404(request: Any, document_id: Any) -> Any:
    row = models.ServiceRequestDocument.objects.filter(
        tenant_id=request.tenant_id, request_id=request.pk, pk=document_id
    ).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


#: A `storage_ref` this product actually put in the document store is a
#: `StoredDocument` id. ⚠ **SOME ARE NOT, AND THAT IS A LIVE FACT RATHER THAN A
#: HYPOTHETICAL (`DEF-CUS-5872`).** Measured on the beta cluster on 2026-09-19:
#: all **six** `service_request_documents` rows carry a ref shaped like
#: `sample-data://cr030/osei-move-in/tenancy-agreement.pdf`, **none of the six
#: resolves to any `stored_documents` row**, every `size` is NULL — and **four
#: of them read `verified`**, which is a clerk having certified a file that does
#: not exist. They are seeded sample rows from `CR-030`.
#:
#: ⚠ **THIS IS EXACTLY THE FAILURE THE OLD SCREEN MESSAGE DESCRIBED** — *"there
#: is nowhere to store it"* — surviving as DATA after the door was built, and it
#: is why the test for this feature reads the BYTES back rather than asserting
#: that a reference is set. **A reference to nothing passes every check that
#: only looks at the column.**
#:
#: Without this guard `download_url(ref)` reaches `UUID('sample-data://…')` and
#: raises **`ValueError`**, which arrives at a clerk as *"Something went wrong
#: on our side"* on a row the screen is showing them. A placeholder is answered
#: as what it is instead: there is no file here yet.
def _stored_document_id(row: Any) -> UUID | None:
    """The real `StoredDocument` id on this row, or `None` for a placeholder."""
    ref = (row.storage_ref or "").strip()
    if not ref:
        return None
    try:
        return UUID(ref)
    except (ValueError, AttributeError, TypeError):
        return None


def has_real_file(row: Any) -> bool:
    """Is there a FILE here — not merely a column with something in it?

    ⚠ **THE PUBLIC NAME FOR THE TEST THIS MODULE ALREADY USES ON EVERY READ
    PATH, EXPORTED SO THERE IS EXACTLY ONE OF IT.** `service_request_reads`
    needs the same answer for the capture wizard's step-4 table, and the
    alternative — re-deriving *"is this ref a UUID"* one module across — is how
    two spellings of one question start disagreeing. `document_link`,
    `fetch_bytes`, `document_dict` and now `documents_tab` all ask this.

    It is deliberately NOT `bool(row.storage_ref)`: six live rows on the beta
    answer True to that and point at nothing (`DEF-CUS-5872`).
    """
    return _stored_document_id(row) is not None


def stored_content_type(row: Any) -> str | None:
    """What the store recorded this row's bytes to be, or `None` with no file.

    `CR-158-BRC10` — one metadata read per filed row, through tenancy's
    published `reference()` (RLS-scoped, never the bytes). A row whose stored
    document cannot be resolved answers `None` rather than failing the tab.
    """
    stored_id = _stored_document_id(row)
    if stored_id is None:
        return None
    try:
        return document_store.reference(stored_id).content_type
    except document_store.DocumentStoreError:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# THE WRITE
# ═══════════════════════════════════════════════════════════════════════════


def attach_file(actor: Any, request_id: Any, payload: dict[str, Any], upload: Any) -> dict:
    """`POST /service-requests/{id}/documents` with a file part — the bytes.

    Two shapes, one code path, and the difference is one optional field:

      * **no `document_id`** — a new attachment row is created carrying the
        file. This is a clerk attaching something at the counter.
      * **a `document_id`** — the file lands on a row that is already there,
        which is the tick a clerk made at step 4 recording what the applicant
        was going to bring. ⚠ **THIS DOCSTRING CLAIMED THE BETA'S SIX ROWS HAD
        A NULL `storage_ref` AND THAT WAS NEVER MEASURED — IT IS FALSE
        (`DEF-CUS-5872`).** Measured 2026-09-19: all six carry a ref shaped
        `sample-data://cr030/…`, **none of the six resolves to a
        `stored_documents` row**, every `size` is NULL and four read
        `verified`. They are seeded placeholders, so this branch is still what
        makes them usable — `_stored_document_id` is what tells a placeholder
        from a real artefact, and filling one is allowed because there are no
        bytes to overwrite.

    ⚠ **A ROW THAT ALREADY HAS A FILE IS REFUSED, AND THE REASON IS THE STORE'S
    GUARANTEE RATHER THAN TIDINESS.** `stored_documents` is write-once under a
    seven-year object lock: the first file cannot be deleted, so "replacing" it
    would leave two artefacts and a row naming one of them, and *"is this the
    document the applicant gave us"* would stop having an answer. A clerk who
    attached the wrong scan attaches the right one as a NEW row and the wrong
    one is rejected with a reason — which the Documents tab already does.

    ⚠ **THE ATTACHMENT ROW'S ID IS MINTED HERE, BEFORE THE DOCUMENT, AND IT IS
    THE DOCUMENT'S `source_id`.** The module docstring argues it; `tenancy/0045`
    is the migration it needs.

    ⚠ **BYTES FIRST, THEN THE ROW**, mirroring `document_store.store()` and
    `account_documents.file_document`. The stored document cannot be deleted, so
    writing the attachment row first and failing the upload would leave a row
    pointing at nothing and nothing could remove it. Written the other way
    round, a failure leaves an object in the bucket that no row names — which is
    invisible and harmless, because nothing lists the bucket.

    ⚠ **THE ROW IS WRITTEN INSIDE A SAVEPOINT — hard-won law 14.** On PostgreSQL
    a failed statement poisons the whole transaction, so a caller that catches an
    `IntegrityError` here without a nested `transaction.atomic()` raises
    `InFailedSqlTransaction` on its very next query. **SQLite has no
    aborted-transaction state and `config/settings/test.py` hardcodes SQLite**,
    so the version without the savepoint passes the entire suite green. Do not
    simplify it away.
    """
    request = _request_or_404(request_id)

    # ── the file, before anything else is decided ──────────────────────────
    if upload is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.documentFileRequired",
            br_ref="BR-SHL-031",
            params={},
        )
    content_type = str(
        payload.get("content_type") or getattr(upload, "content_type", "") or ""
    ).strip().lower()
    # ⚠ `image/jpeg; charset=binary` is a legal header. Compare the media type,
    # never the whole header, or a browser that adds a parameter gets a 415 for
    # a file that is on the list.
    media_type = content_type.split(";")[0].strip()
    if media_type not in ALLOWED_CONTENT_TYPES:
        raise UploadRefused(
            415,
            "customers.serviceRequest.documentTypeNotAllowed",
            br_ref="BR-SHL-031",
            content_type=media_type or "unknown",
            allowed=", ".join(ALLOWED_EXTENSIONS),
        )

    uploaded = upload.read() if hasattr(upload, "read") else bytes(upload or b"")
    if not uploaded:
        # Zero bytes is the shape a failed pick takes, and the store refuses it
        # anyway. Refusing here says which file it was.
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.documentFileRequired",
            br_ref="BR-SHL-031",
            params={},
        )
    if len(uploaded) > MAX_UPLOAD_BYTES:
        # ⚠ **MEASURED ON WHAT ARRIVED, NOT ON WHAT WE WOULD STORE.** The cap is
        # a guard on what this application will accept into memory and pass to a
        # scanner; letting a 40 MB file through because it would compress under
        # 10 MB would defeat it. `BR-WRK-047`'s server-side ceiling is the same
        # reasoning one module across.
        raise UploadRefused(
            413,
            "customers.serviceRequest.documentTooLarge",
            br_ref="BR-SHL-031",
            bytes=str(len(uploaded)),
            max_mb=str(MAX_UPLOAD_BYTES // (1024 * 1024)),
        )

    # ── which row is this going on ─────────────────────────────────────────
    existing_id = payload.get("document_id") or None
    row = _row_or_404(request, existing_id) if existing_id else None
    # ⚠ **`_stored_document_id`, NOT `row.storage_ref` — the seeded rows would
    # otherwise be STRANDED (`DEF-CUS-5872`).** A placeholder ref holds no bytes,
    # so filling it is not "replacing" a filed document and there is nothing the
    # write-once guarantee protects. The refusal below is about REAL artefacts.
    if row is not None and _stored_document_id(row) is not None:
        raise errors.BizError(
            errors.BIZ_LOCKED,
            message_key="customers.serviceRequest.documentAlreadyHasFile",
            br_ref="NFR-35",
            params={"doc_type": row.doc_type},
        )

    doc_type = str(payload.get("doc_type") or (row.doc_type if row else "") or "").strip()
    if doc_type not in models.ServiceRequestDocument.ATTACHABLE_DOC_TYPES:
        # `BR-CUS-095` — a closed vocabulary, because a tick can only be
        # satisfied if the thing attached carries the same name as the thing
        # ticked. Free text would let a utility require `proof_of_identity`
        # while every clerk attaches `photo_id`.
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.documentTypeUnknown",
            br_ref="BR-CUS-095",
            params={"value": doc_type},
        )

    name = str(payload.get("name") or getattr(upload, "name", "") or "").strip()
    if not name:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.documentNameRequired",
            br_ref="BR-SHL-031",
            params={},
        )

    # ── REDUCE ONCE, HERE, BEFORE ANYTHING IS FILED ────────────────────────
    reduction = document_shrink.reduce_on_the_way_in(uploaded, media_type)

    card_id = row.id if row is not None else uuid7()
    moment = timezone.now()

    # ⚠ **THE DISPLAY NAME IS COMPOSED HERE AND NOWHERE ELSE, BECAUSE ONLY
    # CUSTOMERS CAN.** `document_store._require_display_name` refuses to invent
    # one and says why: a usable name needs the request's number, which lives in
    # this module's table. The shape mirrors the storage key so an unpacked
    # export reads like the bucket — `<kind>/<yyyy>/<mm>/<human reference>`.
    reference = (getattr(request, "request_no", "") or str(request.pk)).strip()
    safe = name.replace("/", "-").replace("\\", "-").lstrip(".")
    display_name = f"service-request-documents/{moment:%Y}/{moment:%m}/{reference}-{safe}"

    ref = document_store.store(
        kind=KIND_SERVICE_REQUEST_DOCUMENT,
        source_type=SOURCE_SERVICE_REQUEST_DOCUMENT,
        source_id=card_id,
        content_type=media_type,
        display_name=display_name,
        payload=reduction.payload,
        actor_user_id=_actor_id(actor),
        process=None if _actor_id(actor) else "customers.service_request_documents",
    )

    # ⚠ A SAVEPOINT, NOT A CONVENIENCE — hard-won law 14. See the docstring.
    with transaction.atomic():
        if row is None:
            row = models.ServiceRequestDocument.objects.create(
                id=card_id,
                tenant_id=request.tenant_id,
                request=request,
                doc_type=doc_type,
                what_it_proves=(payload.get("what_it_proves") or None),
                document_number=(payload.get("document_number") or None),
                required_flag=bool(payload.get("required", False)),
                # ⚠ **ALWAYS `not_checked`.** Attaching is not verifying — the
                # detail's own BLOCKING callout. A file that arrived pre-verified
                # would be a clerk certifying something nobody looked at.
                verification_state=models.ServiceRequestDocument.NOT_CHECKED,
            )
        row.name = name
        row.size = reduction.stored_bytes
        # ⚠ NULL WHEN NOTHING WAS DONE. See the column's own comment — a value
        # that always equalled `size` could not tell an untouched file from a
        # shrunk one, which is the only question it exists to answer.
        row.original_size = reduction.original_bytes if reduction.reduced else None
        row.storage_ref = str(ref.id)
        row.uploaded_by_id = _actor_id(actor)
        row.uploaded_at = moment
        row.save(
            update_fields=[
                "name",
                "size",
                "original_size",
                "storage_ref",
                "uploaded_by",
                "uploaded_at",
            ]
        )

    # Hard rule 7 covers MONEY actions and attaching a document is not one. A row
    # is written anyway, for the reason `account_documents` gives one table
    # across: a document filed against a supply decision is evidence about that
    # decision, and the store's own `document.stored` row cannot name the
    # REQUEST — it does not know what a service request is.
    core_audit.write_row(
        action="customers.service_request_document.attached",
        entity_type="service_request_document",
        entity_id=row.id,
        actor_user_id=_actor_id(actor),
        after={
            "request_id": str(request.pk),
            "doc_type": doc_type,
            "document_id": str(ref.id),
            "display_name": display_name,
            "content_type": media_type,
            "stored_bytes": reduction.stored_bytes,
            # ⚠ Written on EVERY row, reduced or not, and `None` when nothing
            # was done. An audit that recorded the pair only when they differed
            # could not answer *"was this file touched?"* — it could only answer
            # *"was it touched and did somebody write it down?"*
            "original_bytes": reduction.original_bytes if reduction.reduced else None,
            "reduction": reduction.method,
        },
    )
    return document_dict(row)


#: ⚠ **WHICH DESIGNED TYPE A PORTAL APPLICANT'S FILE IS — `DEF-CWP-9167`.**
#: PO ruling 2026-10-02 (option A): *"a separate attach row for each
#: requirement (Photo ID, Proof of address), so it's always clear what each file
#: is for"*. The portal asks for two documents (`portal.applications.
#: DOCUMENT_REQUIREMENTS`) and each file now says which; here each becomes one
#: of `BR-CUS-095`'s designed types, so the clerk's Documents tab reads *Proof
#: of identity* and *Proof of address or occupancy* instead of two *Other* rows,
#: and a tenant's required-document checklist can be met by them. A file with
#: no requirement (attached before the portal asked) stays `other`.
#: ⊕ `DEF-CUS-9834` — the process name a portal hand-over stores its files
#: under (`stored_documents.stored_by_process`). It is how a read knows the
#: APPLICANT brought a file whose `uploaded_by` is empty by design (nobody on
#: staff uploaded it): `service_request_reads.documents_tab` names them.
PORTAL_STORE_PROCESS = "portal.application_documents"

PORTAL_REQUIREMENT_DOC_TYPES: dict[str, str] = {
    "photo_id": models.ServiceRequestDocument.DOC_PROOF_OF_IDENTITY,
    "proof_of_address": models.ServiceRequestDocument.DOC_PROOF_OF_ADDRESS,
}


def attach_from_portal(request_id: Any, files: list[dict[str, Any]]) -> list[dict]:
    """The applicant's files, filed on the request the portal just created —
    `CR-158-BRC10` (PO 2026-10-01: *"save those document to server for that
    Utility - and then clark should able to view those document in new
    request"*).

    ⚠ **A SECOND, NARROWER DOOR BESIDE `attach_file`, FOR THE REASON
    `create_from_portal` IS ONE BESIDE `create_request`.** There is nobody
    signed in; the portal must not fabricate a clerk to get through the staff
    door. So this takes ONLY what a portal hand-over carries — a name, the
    media type the BYTES were found to be (the portal sniffs; it never trusts
    the browser) and the bytes — and decides everything else itself:

      * `doc_type` is what the applicant attached it AS — the attach row it was
        chosen on (`PORTAL_REQUIREMENT_DOC_TYPES`, `DEF-CWP-9167`) — and
        `other` for a file with no requirement; the state below still says
        nobody has checked it;
      * the state is `not_checked`, always: *"attaching a file is not the same
        as verifying it"*;
      * `uploaded_by` is empty — no staff member uploaded it — and
        `uploaded_at` is when the APPLICANT uploaded it, not when it was sent.

    ⚠ **THE ROW'S ID IS THE PORTAL ROW'S ID**, so the stored document's
    `source_id`, this attachment and the audit row of the original upload all
    name one thing — and the module docstring's reason (a second PDF on one
    request must not collide on `uq_stored_documents_filed`) holds unchanged.

    ⚠ **THE SAME GUARDS AS `attach_file`, NOT FEWER**: the allowlist and the
    cap are re-checked here, because this module does not take another
    module's word for what it files.
    """
    request = _request_or_404(request_id)
    out: list[dict] = []
    for item in files:
        media_type = str(item.get("content_type") or "").split(";")[0].strip().lower()
        uploaded = bytes(item.get("payload") or b"")
        name = str(item.get("name") or "").strip() or "document"
        if media_type not in ALLOWED_CONTENT_TYPES or not uploaded:
            raise UploadRefused(
                415,
                "customers.serviceRequest.documentTypeNotAllowed",
                br_ref="BR-SHL-031",
                content_type=media_type or "unknown",
                allowed=", ".join(ALLOWED_EXTENSIONS),
            )
        if len(uploaded) > MAX_UPLOAD_BYTES:
            raise UploadRefused(
                413,
                "customers.serviceRequest.documentTooLarge",
                br_ref="BR-SHL-031",
                bytes=str(len(uploaded)),
                max_mb=str(MAX_UPLOAD_BYTES // (1024 * 1024)),
            )
        reduction = document_shrink.reduce_on_the_way_in(uploaded, media_type)
        card_id = item.get("id") or uuid7()
        moment = item.get("uploaded_at") or timezone.now()
        reference = (getattr(request, "request_no", "") or str(request.pk)).strip()
        safe = name.replace("/", "-").replace("\\", "-").lstrip(".")
        display_name = f"service-request-documents/{moment:%Y}/{moment:%m}/{reference}-{safe}"
        ref = document_store.store(
            kind=KIND_SERVICE_REQUEST_DOCUMENT,
            source_type=SOURCE_SERVICE_REQUEST_DOCUMENT,
            source_id=card_id,
            content_type=media_type,
            display_name=display_name,
            payload=reduction.payload,
            actor_user_id=None,
            process=PORTAL_STORE_PROCESS,
        )
        # ⚠ A SAVEPOINT — hard-won law 14, as in `attach_file`.
        with transaction.atomic():
            row = models.ServiceRequestDocument.objects.create(
                id=card_id,
                tenant_id=request.tenant_id,
                request=request,
                doc_type=PORTAL_REQUIREMENT_DOC_TYPES.get(
                    str(item.get("requirement") or ""),
                    models.ServiceRequestDocument.DOC_OTHER,
                ),
                verification_state=models.ServiceRequestDocument.NOT_CHECKED,
                name=name,
                size=reduction.stored_bytes,
                original_size=reduction.original_bytes if reduction.reduced else None,
                storage_ref=str(ref.id),
                uploaded_at=moment,
            )
        core_audit.write_row(
            action="customers.service_request_document.attached_from_portal",
            entity_type="service_request_document",
            entity_id=row.id,
            after={
                "request_id": str(request.pk),
                "document_id": str(ref.id),
                "display_name": display_name,
                "content_type": media_type,
                "stored_bytes": reduction.stored_bytes,
                "original_bytes": reduction.original_bytes if reduction.reduced else None,
                "reduction": reduction.method,
            },
        )
        out.append(document_dict(row))
    return out


#: `CR-158-BRC10`'s figure, the same on both doors: an application carries at
#: most FIVE files of the applicant's own, and a reply to *Ask for more* counts
#: against the same five — it is one application answering one question.
MAX_APPLICANT_DOCUMENTS = 5


def applicant_documents_held(request_id: Any) -> int:
    """How many files the APPLICANT has put on this request — the rows no staff
    member uploaded (`uploaded_by` empty), which is how both portal doors write
    them. A clerk's own scans do not count against the applicant's five."""
    return models.ServiceRequestDocument.objects.filter(
        tenant_id=_tenant_id(), request_id=request_id, uploaded_by__isnull=True
    ).count()


def attach_reply_from_portal(request_id: Any, *, name: str, content_type: str, payload: bytes) -> dict:
    """`DEF-CWP-9049` — **the applicant answers *Ask for more* with a file**,
    from the Track page, and it lands on the request a clerk is waiting on.

    Until 2026-10-02 a clerk could ask for a clearer ID and the applicant had
    nowhere to send it: Track said *More info needed* and nothing else, and the
    application's own upload door refuses once the application is sent (409).
    The walk of that date measured it (W14: two files on the request, never
    three).

    **ONLY A REQUEST IN `more_info` TAKES ONE.** Every other state refuses by
    name — a submitted request has not been asked anything, and an approved or
    refused one is decided. The state does NOT move: `TRANSITIONS` lets a clerk
    decide straight from `more_info` the moment the answer arrives, which is
    why `info_received` was retired. What the clerk sees instead is the file on
    the Documents tab and a `customer_replied` row on History, visible to the
    customer too because it is their own act (`BR-CWP-078`).

    The bytes go through `attach_from_portal` — the same allowlist, cap,
    shrink, store and audit as the files sent with the application — and the
    five-file figure is checked under a lock on the request so two tabs cannot
    both send the fifth.
    """
    from apps.customers import service_request_service

    with transaction.atomic():
        request = (
            models.ServiceRequest.objects.select_for_update()
            .filter(tenant_id=_tenant_id(), pk=request_id)
            .first()
        )
        if request is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        if request.state != models.ServiceRequest.MORE_INFO:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="DEF-CWP-9049",
                message_key="portal.track.replyNotAsked",
                params={},
            )
        if applicant_documents_held(request.pk) >= MAX_APPLICANT_DOCUMENTS:
            raise errors.ValidationError(
                errors.VAL_RANGE,
                message_key="portal.application.documentLimit",
                params={"name": name, "max": MAX_APPLICANT_DOCUMENTS},
            )
        filed = attach_from_portal(
            request.pk, [{"name": name, "content_type": content_type, "payload": payload}]
        )
        service_request_service.note_from_portal(
            request.pk,
            note=name,
            note_type="customer_replied:document",
            customer_visible=True,
        )
        core_audit.write_row(
            action="service_request.customer_replied",
            entity_type="service_request",
            entity_id=request.pk,
            after={"document_id": filed[0]["id"], "name": name, "content_type": content_type},
        )
    return filed[0]


# ═══════════════════════════════════════════════════════════════════════════
# THE READ
# ═══════════════════════════════════════════════════════════════════════════


def document_dict(row: Any) -> dict[str, Any]:
    """One attachment, as a screen sees it.

    ⚠ **B14 RULE 31 — NO CELL HERE IS EVER A DATABASE ID.** `id` is the React
    key and the address of the download link; the visible name is what the clerk
    typed. `storage_ref` is deliberately **not served**: it is a reference into
    tenancy's table and a screen has no use for it, while a payload carrying it
    is a payload somebody eventually renders.

    ⚠ **THE SIZES ARE SERVED AS NUMBERS, NOT FORMATTED STRINGS.** The screen
    formats them — one formatter, the shared kit's — because a server that
    returns "1.2 MB" has decided a locale's decimal separator on the server,
    which is the mistake `BR-SHL-034` records for dates.
    """
    return {
        "id": str(row.id),
        "doc_type": row.doc_type,
        "what_it_proves": row.what_it_proves,
        "document_number": row.document_number,
        "name": row.name,
        # ⚠ **A REAL ARTEFACT, NOT MERELY A NON-EMPTY COLUMN (`DEF-CUS-5872`).**
        # `bool(row.storage_ref)` answers True for all six of the beta's seeded
        # placeholders, so a screen reading it would show a paperclip against a
        # file nobody can open — the same lie one level up from the one this
        # module's read paths refuse.
        #
        # ⚠ **`service_request_reads.documents_tab` STILL USES THE OLD TEST AND
        # WAS DELIBERATELY NOT CHANGED.** Its `attached` and `verified` counts
        # drive a live screen ("2 of 3 verified"), so moving them is a
        # maintenance fix with its own reproduce step and blast radius, not a
        # change to make in passing from a build lane. It is named in
        # `DEF-CUS-5872`'s prevention column.
        "attached": _stored_document_id(row) is not None,
        "size_bytes": row.size,
        # ⚠ `None` MEANS "STORED EXACTLY AS IT ARRIVED", not "unknown". A screen
        # shows the pair only when this is set, which is how a clerk is told why
        # the 3.1 MB file they chose is 400 KB on disk.
        "original_size_bytes": row.original_size,
        "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
        "required": row.required_flag,
        "verification_state": row.verification_state,
        "reject_reason": row.reject_reason,
    }


def document_link(request_id: Any, document_id: Any) -> dict[str, Any]:
    """`GET /service-requests/{id}/documents/{docId}/download` — a link that dies.

    ⚠ **THE ROW IS RESOLVED UNDER THIS TENANT FIRST, AND THEN THE URL IS
    MINTED.** Order matters and it is the order `account_documents.document_link`
    and `work.evidence` both use: a link is never issued for a document the
    caller could not have found. Another utility asking for this file gets a 404
    — the same answer as for one that does not exist (`BR-TEN-003`, HR-1).

    ⚠ **THE LINK IS A BEARER TOKEN.** `document_store.download_url` mints it at
    `document_storage.url_ttl_seconds()`, capped at four hours by the PO ruling
    of 2026-08-30. Whoever holds the URL reads this one file with no session
    until it expires; if a link needs to outlive that, issue a new one.
    """
    request = _request_or_404(request_id)
    row = _row_or_404(request, document_id)
    stored_id = _stored_document_id(row)
    if stored_id is None:
        # A tick with no file, OR a seeded placeholder ref (`DEF-CUS-5872`).
        # **Not a 404** — the row is really there and the
        # clerk is looking at it; saying "not found" would send them hunting for
        # a row they can see. This is the same distinction `document_store`
        # draws between `document_not_stored` and a missing object.
        # ⚠ `BizError`, NOT `ValidationError` — `BIZ_COMPLETENESS` is a BIZ
        # catalog code and `ValidationError.allowed_codes` is VAL_CODES, so a
        # ValidationError carrying it raises `ValueError` at the raise site
        # (B12 §3 G1: no endpoint invents a code).
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            message_key="customers.serviceRequest.documentHasNoFile",
            br_ref="BR-SHL-031",
            params={"doc_type": row.doc_type},
        )

    from apps.tenancy import document_storage

    payload = document_dict(row)
    payload["url"] = document_store.download_url(stored_id)
    payload["expires_in_seconds"] = document_storage.url_ttl_seconds()
    return payload


def fetch_bytes(request_id: Any, document_id: Any) -> bytes:
    """The exact bytes that were stored, hash-checked by the store on the way out.

    Used by the proof and by anything that must hold the file rather than hand
    out a link. It re-resolves through the same two tenant-scoped lookups as
    `document_link`, so it cannot reach another utility's document either.
    """
    request = _request_or_404(request_id)
    row = _row_or_404(request, document_id)
    stored_id = _stored_document_id(row)
    if stored_id is None:
        # A tick with no file, OR a seeded placeholder ref (`DEF-CUS-5872`).
        # ⚠ `BizError`, NOT `ValidationError` — `BIZ_COMPLETENESS` is a BIZ
        # catalog code and `ValidationError.allowed_codes` is VAL_CODES, so a
        # ValidationError carrying it raises `ValueError` at the raise site
        # (B12 §3 G1: no endpoint invents a code).
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            message_key="customers.serviceRequest.documentHasNoFile",
            br_ref="BR-SHL-031",
            params={"doc_type": row.doc_type},
        )
    return document_store.fetch(stored_id)


#: The two ways a clerk opens a file, and the audit verb each writes.
CONTENT_VIEW = "view"
CONTENT_DOWNLOAD = "download"
CONTENT_MODES = (CONTENT_VIEW, CONTENT_DOWNLOAD)

#: The types a browser may DRAW in a tab. Anything else on a request (a CSV a
#: clerk filed) is always sent as a download, never rendered.
INLINE_CONTENT_TYPES = ("application/pdf", "image/png", "image/jpeg")


def document_content(actor: Any, request_id: Any, document_id: Any, mode: str) -> dict[str, Any]:
    """The bytes of one filed document, for `GET …/documents/{docId}/content`.

    `CR-158-BRC10` (PO 2026-10-01: *"clark should able to view those document
    in new request"*). ⚠ **WHY THE BYTES COME THROUGH THIS APPLICATION FOR ONE
    FILE**, when the store's docstring says a bulk export must never proxy:
    that rule is about half a million files; this is one, and passing through
    here is what lets the response carry `Content-Disposition`, `nosniff` and a
    script-forbidding policy that a bare object-store link does not. It is
    `notifications/reprint_api.py`'s trade for a single document, made for the
    same reason. It also works on the filesystem backend, whose `file://` link
    a browser refuses (`openStoredDocument.ts`).

    Resolved under THIS tenant first (`_request_or_404`, `_row_or_404`): another
    utility's clerk asking for this file gets the 404 a missing one gets.

    Every call writes `audit_log` — `…viewed` or `…downloaded` — naming the
    request, the file and who asked (PO 2026-10-01; hard rule 7's posture for
    evidence, as `attach_file` already takes).
    """
    if mode not in CONTENT_MODES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.documentModeUnknown",
            br_ref="CR-158-BRC10",
            params={"value": str(mode)},
        )
    request = _request_or_404(request_id)
    row = _row_or_404(request, document_id)
    stored_id = _stored_document_id(row)
    if stored_id is None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            message_key="customers.serviceRequest.documentHasNoFile",
            br_ref="BR-SHL-031",
            params={"doc_type": row.doc_type},
        )
    reference = document_store.reference(stored_id)
    payload = document_store.fetch(stored_id)
    content_type = (reference.content_type or "").split(";")[0].strip().lower()
    inline = mode == CONTENT_VIEW and content_type in INLINE_CONTENT_TYPES
    core_audit.write_row(
        action=(
            "customers.service_request_document.viewed"
            if mode == CONTENT_VIEW
            else "customers.service_request_document.downloaded"
        ),
        entity_type="service_request_document",
        entity_id=row.id,
        actor_user_id=_actor_id(actor),
        after={
            "request_id": str(request.pk),
            "document_id": str(stored_id),
            "name": row.name,
            "content_type": content_type,
            "bytes": len(payload),
        },
    )
    return {
        "payload": payload,
        "content_type": content_type if content_type in ALLOWED_CONTENT_TYPES else "application/octet-stream",
        "name": row.name or "document",
        "inline": inline,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: the PO's "you will have to reduce the size and save them on cloud container etc" · BR-SHL-031 (CONFIRMED) · BR-CUS-095 · BR-WRK-047 · NFR-33 / NFR-35 · 11b G11 · B2 §2 · apps/customers/account_documents.py (the worked precedent, one table across)
# generated: 2026-09-19 by the service-request-documents lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — step 4 of the capture wizard is a later lane; 07-frontend/src/features/customers/ServiceRequestCapturePage.tsx is owned by a sibling lane and was not touched) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the second-PDF case was shown refused by uq_stored_documents_filed with the request as source_id and passing with the attachment row as source_id; the byte-for-byte readback was shown failing before store() was wired and passing after; a cross-tenant download was shown returning the link before the tenant-scoped resolve and 404 after.
# exceptions: (1) `source_id` IS THE ATTACHMENT ROW, NOT THE REQUEST — argued in the module docstring; the unique constraint is not widened. (2) THE REDUCTION IS LOSSLESS ONLY — core/document_shrink.py argues it and the decision log records the figure a lossy path would have bought. (3) A row that already has a file is REFUSED rather than replaced, because the bytes are write-once. (4) An audit row is written though hard rule 7 covers money actions only.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

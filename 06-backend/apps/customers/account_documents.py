# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 step 2 wave I — `ACC-S8`, "An account can hold a
#           document". The read and the write behind tab `ACC-T10`.
# Story:    US-CUS-011 · screen S21.
# Rules:    BR-CUS-036 (CONFIRMED — the table, the five-value type lookup,
#           "system/contract docs audit-locked") · BR-SHL-031 (CONFIRMED —
#           "upload guards (PDF/PNG/JPG/CSV allowlist, 10MB tenant-config,
#           malware scan pre-acceptance); legal class WRITE-ONCE 7yr; v1
#           uploads staff-mediated" — its scan clause SUPERSEDED by the PO,
#           2026-09-22/23, DEF-SHL-6347) · 11b G11 (413 over the cap, 415 outside
#           the allowlist) · NFR-3 (universal server pagination) · NFR-5 (no
#           hard caps) · NFR-33/NFR-35 · BR-SHL-025 (a forbidden control is
#           disabled WITH its reason) · BR-TEN-003 (existence must not leak) ·
#           CLAUDE.md hard rule 1 · hard rule 7 (audit) · hard-won law 14 (a
#           failed statement poisons the whole PostgreSQL transaction).
# Tests:    06-backend/tests/test_cr094_i_account_documents.py
# Impacts:  apps/customers/api.py (GET/POST /accounts/{id}/documents,
#           GET /accounts/{id}/documents/{docId}) ·
#           07-frontend/src/features/customers/accountDetailTabs.tsx
# ───────────────────────────────────────────────────────
"""Filing a document on an account, and listing what is filed.

THE ONE THING THIS MODULE DOES NOT DO IS STORE A FILE
──────────────────────────────────────────────────────────────────────────────
Every byte goes to `apps.tenancy.document_store.store()`, which this product has
had since `CR-049` task 1 and which already does the hard parts: the object
store behind a seam, the sha256 written and re-checked on the way back, the
seven-year object lock (⚠ the object LOCK is suspended from 2026-10-02, `CR-160-BRC10`; the row stays write-once),
the write-once trigger, the RLS-scoped read that is the
**only** way a storage key can ever be learned. Nothing here composes a key,
accepts a key, or touches a bucket.

**That is the PO's standing instruction for this wave, applied rather than
quoted:** *"Do all changes based on actual code — also don't create duplicate
code."* A second storage path for customer files would have been the easy thing
to write and the thing that makes *"which copy is the document"* have two
answers.

WHAT THE GUARDS ARE, AND WHERE EACH NUMBER COMES FROM
──────────────────────────────────────────────────────────────────────────────
`BR-SHL-031` is CONFIRMED (PO DF-1..4, 2026-08-08) and is quoted verbatim in the
trace block above. Nothing here is chosen:

  * **the allowlist is PDF · PNG · JPG · CSV** → anything else is **415**;
  * **the cap is 10 MB** → anything larger is **413**;
  * **uploads are staff-mediated in v1** → the endpoint takes `AdminOrClerk`,
    and there is no portal door.

⚠ **THERE IS NO VIRUS SCAN, AND THAT IS A PO RULING RATHER THAN A GAP.**
`BR-SHL-031`'s *"malware scan pre-acceptance"* clause went unbuilt until
2026-09-13, when `BR-SHL-253` put a scanner daemon in front of every multipart
upload; the PO then removed the scan on 2026-09-22 and 2026-09-23 (*"please
remove virus scan chek user don't wan't it"*, `DEF-SHL-6347`). So nothing
between the clerk's file and the store looks inside it: the allowlist and the
cap above are the whole of the upload guard, and neither is a scan.

⚠ **AND THE CAP IS A CONSTANT WHERE THE RULE SAYS "10MB TENANT-CONFIG".** The
figure is the rule's; the per-tenant SETTING is not built, because no settings
family declares it and inventing a settings key is how two spellings of one
option appear. A tenant that needs a different cap is a settings row and a
migration, and `MAX_UPLOAD_BYTES` is the single place it would be read from.

WHY THE LIST IS PAGED IN SQL AND NOT IN PYTHON
──────────────────────────────────────────────────────────────────────────────
`NFR-3` — universal server pagination — and `CLAUDE.md` counts **four** live
breaches that all named the old 3,000-connection ceiling as their excuse
(`DEF-PAY-4221`). This is a new list and it is not the fifth. `documents_page`
returns `(one page, COUNT(*))` over `ix_account_documents_recent`; nothing here
materialises a whole account's filings to draw ten of them, and there is **no
cap of any kind** on how many an account may hold (`NFR-5`).
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.customers import models
from apps.customers.account_document_models import (
    AUDIT_LOCKED_TYPES,
    DOCUMENT_TYPES,
    UPLOADABLE_TYPES,
    WITHDRAWABLE_TYPES,
    AccountDocument,
)
from apps.tenancy import document_store
from apps.tenancy.document_models import KIND_ACCOUNT_DOCUMENT, SOURCE_ACCOUNT_DOCUMENT
from core import audit as core_audit
from core import errors
from core.dbfields import uuid7
from core.pagination import ListParams, order_terms
from core.tenancy import current_tenant_id

# ═══════════════════════════════════════════════════════════════════════════
# THE GUARDS — `BR-SHL-031`, quoted rather than chosen
# ═══════════════════════════════════════════════════════════════════════════

#: *"10MB tenant-config"*. The tenant half is not built — see the module
#: docstring. 10 MiB, because a 10 MB cap a clerk meets at 10,485,760 bytes is
#: the one every other tool in this class uses and the rule does not
#: distinguish.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

#: *"PDF/PNG/JPG/CSV allowlist"*. ⚠ **BOTH SPELLINGS OF A JPEG AND BOTH OF A
#: CSV**, because a browser sends `image/jpeg` and some scanners send
#: `image/jpg`, and Excel sends `application/vnd.ms-excel` for a file a person
#: calls a CSV. Refusing a file for the spelling of its type would be a 415 a
#: clerk cannot act on.
ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "text/csv": "csv",
    "application/csv": "csv",
    "application/vnd.ms-excel": "csv",
}

#: What a clerk sees when a file is refused — the EXTENSIONS, not the media
#: types, because `application/vnd.ms-excel` is not a sentence anybody can act
#: on. B14 rule 33 caps a FACT at six words; this is a parameter in a message,
#: not the message.
ALLOWED_EXTENSIONS = ("PDF", "PNG", "JPG", "CSV")

#: THE SORTS the tab offers. `uploaded` is the default and it is DESCENDING —
#: `BR-CUS-1046` (PO 2026-09-10): *"The new newly created entries should always
#: show on the top."* A filing cabinet opening on the oldest scan is the exact
#: inversion that ruling exists to remove.
DOCUMENT_SORTS = ("uploaded", "name", "type")
DOCUMENT_DEFAULT_SORT = "uploaded"
DOCUMENT_DEFAULT_DIR = "desc"
DOCUMENT_FILTERS = ("type",)

#: Each written ASCENDING; `order_terms` flips every term for `desc`, so the two
#: directions of one column cannot drift apart.
_SORT_COLUMNS: dict[str, tuple[Any, ...]] = {
    "uploaded": ("uploaded_at", "id"),
    "name": ("document__display_name", "id"),
    "type": ("doc_type", "id"),
}


class UploadRefused(Exception):
    """A **413** or a **415** — a B12 r1 transport row with no catalog code.

    ⚠ **RAISED FROM THE SERVICE AND MAPPED IN THE API, NOT THE OTHER WAY
    ROUND.** `apps/tenancy/api.py` checks the logo's allowlist and cap in the
    ENDPOINT and re-runs the law inside the service so *"a job or shell caller
    cannot bypass it"*. This puts the guard in ONE place — here — and carries
    the status out with the refusal, so there is no second implementation to
    keep in step and no path that reaches `document_store.store()` unguarded.

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


def _account_or_404(account_id: Any) -> Any:
    """The account, under THIS tenant — or the same answer as "never existed".

    ⚠ Resolved BEFORE anything else, on every path. A caller in another tenant
    asking about an account it cannot see gets a 404, not a 403: a 403 confirms
    the account exists (`BR-TEN-003`, HR-1 — existence must not leak).
    """
    row = models.Account.objects.filter(tenant_id=_tenant_id(), pk=account_id).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None)


# ═══════════════════════════════════════════════════════════════════════════
# THE READ
# ═══════════════════════════════════════════════════════════════════════════


def documents_page(account_id: Any, params: ListParams) -> tuple[list[dict[str, Any]], int]:
    """One page of this account's filings, and the whole set's count (`NFR-3`).

    The count is a `COUNT(*)` over the same queryset, so a clerk on page 1 of a
    landlord's four hundred filings is told there are four hundred without four
    hundred rows being built. `select_related` fetches the stored document and
    the uploader in the same query — `DOCUMENT`, `SIZE` and `UPLOADED BY` are
    three of the five columns `ACC-T10` draws, and an N+1 here would be one
    round trip per row.
    """
    account = _account_or_404(account_id)
    qs = AccountDocument.objects.filter(
        tenant_id=account.tenant_id,
        account_id=account.pk,
        # ⚠ **`BR-CUS-1052` LIVES HERE AS MUCH AS IN THE WRITE.** *Withdrawn*
        # means the account no longer holds the document, so it is not listed
        # AND NOT COUNTED — the `COUNT(*)` below runs over this same queryset,
        # which is why the filter goes on the queryset and never on the slice.
        # A tab that hid a row and still said "11 documents" would be the
        # withdrawal failing in the only place a clerk could see it.
        withdrawn_at__isnull=True,
    ).select_related("document", "uploaded_by")

    wanted = (params.filters.get("type") or "").strip().lower()
    if wanted in DOCUMENT_TYPES:
        qs = qs.filter(doc_type=wanted)
    # ⚠ An UNRECOGNISED type does not filter at all — `BR-SHL-011`, clamp never
    # error. A chip spelled wrong by a client must not empty a clerk's table.

    term = (params.q or "").strip()
    if term:
        qs = qs.filter(document__display_name__icontains=term)

    qs = qs.order_by(
        *order_terms(
            params.sort, params.dir, columns=_SORT_COLUMNS, default=DOCUMENT_DEFAULT_SORT
        )
    )

    total = qs.count()
    start = max(params.page - 1, 0) * params.per
    return [_document_dict(row, account.account_no) for row in qs[start : start + params.per]], total


def _visible_name(display_name: Any, account_no: Any) -> str:
    """The name the CLERK typed, read back out of the storage-shaped one.

    ⚠ **THE `DOCUMENT` CELL WAS SHOWING A STORAGE PATH (`DEF-CUS-5147`).**
    `file_document` composes `display_name` as
    `account-documents/<yyyy>/<mm>/<account_no>-<what the clerk typed>` — on
    purpose, so an unpacked export reads like the bucket — and `_document_dict`
    served that whole string as `name`. `ACC-T10` draws `Ten-day notice —
    DSC-26-0003` in that column; the running screen drew
    `account-documents/2026/09/AC-2026-00052-Ten-day notice`. It is B14 rule
    31's reasoning one step out: the visible value must be the thing a person
    named, never the address the product keeps it at.

    ⚠ **THE STORED NAME DOES NOT MOVE.** Nothing about the export, the key or
    the uniqueness constraint changes; only what the LIST hands a screen. The
    prefix is stripped by NAME rather than by counting separators, because an
    account number contains hyphens and a document name may contain slashes
    (`file_document` replaces those, which is why the leaf is safe to take).

    Found by looking at the tab in a browser — hard-won law 6 — and by nothing
    else: the conformance check measures column HEADS, and every test asserted
    the string it was given.
    """
    leaf = str(display_name or "").rsplit("/", 1)[-1]
    prefix = f"{str(account_no or '').strip()}-"
    return leaf[len(prefix) :] if prefix != "-" and leaf.startswith(prefix) else leaf


def _document_dict(row: Any, account_no: Any = None) -> dict[str, Any]:
    """One row of `ACC-T10`, in the drawing's own column order.

    ⚠ **B14 RULE 31 — NO CELL HERE IS EVER A DATABASE ID.** `id` is the React
    key and the address of the download link; the visible `DOCUMENT` cell is
    `display_name`, which the writer supplied and which
    `document_store._require_display_name` refused to invent.

    ⚠ **`size_bytes` IS SERVED AS A NUMBER, NOT A FORMATTED STRING.** The
    screen formats it — one formatter, the shared kit's — because a server that
    returns "1.2 MB" has decided a locale's decimal separator on the server,
    which is the mistake `BR-SHL-034` records for dates.
    """
    document = row.document
    uploader = row.uploaded_by
    name = (getattr(uploader, "full_name", "") or getattr(uploader, "email", "") or "").strip()
    return {
        "id": str(row.id),
        "name": _visible_name(document.display_name, account_no),
        "doc_type": row.doc_type,
        "uploaded_at": row.uploaded_at,
        # ⚠ NEVER an empty string where a person is expected — rule 31's
        # reasoning applies to a blank as much as to a uuid: a clerk reads an
        # empty cell as "nobody", and for a system-filed document the honest
        # answer is the PROCESS that filed it.
        "uploaded_by_name": name or None,
        "uploaded_by_process": row.uploaded_by_process or None,
        "size_bytes": document.byte_length,
        "content_type": document.content_type,
    }


def _live_filing(account: Any, document_id: Any) -> Any:
    """This account's filing, still on the account — or the 404 of a stranger.

    ⚠ **ONE LOOKUP SERVES THE READ AND THE WITHDRAWAL, AND THAT IS THE POINT
    RATHER THAN TIDINESS.** Three different things must be indistinguishable to
    a caller here, and writing the filter twice is how one of them stops being:

      * a filing in ANOTHER TENANT (`BR-TEN-003`, HR-1 — existence must not
        leak);
      * a filing on ANOTHER ACCOUNT of this tenant;
      * a filing THIS TENANT ALREADY WITHDREW (`BR-CUS-1052`).

    All three answer 404. The third is the new one and it is deliberate: after a
    withdrawal the account does not hold that document, so *"there is no such
    document on this account"* is the literal truth, and a second withdrawal
    from a stale tab gets the same answer as a first one from a stranger.
    """
    row = (
        AccountDocument.objects.filter(
            tenant_id=account.tenant_id,
            account_id=account.pk,
            id=document_id,
            withdrawn_at__isnull=True,
        )
        .select_related("document", "uploaded_by")
        .first()
    )
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def document_link(account_id: Any, document_id: Any) -> dict[str, Any]:
    """`GET /accounts/{id}/documents/{docId}` — a link that dies.

    ⚠ **THE ROW IS RESOLVED UNDER THIS TENANT FIRST, AND THEN THE URL IS
    MINTED.** Order matters and it is the same order `work.evidence` uses: a
    link is never issued for a document the caller could not have found. Another
    utility asking for this file gets a 404 — the same answer as for one that
    does not exist.

    ⚠ **THE LINK IS A BEARER TOKEN.** `document_store.download_url` mints it at
    `document_storage.url_ttl_seconds()`, capped at four hours by the PO ruling
    of 2026-08-30. Whoever holds the URL reads this one file with no session
    until it expires; if a link needs to outlive that, issue a new one.
    """
    account = _account_or_404(account_id)
    row = _live_filing(account, document_id)

    from apps.tenancy import document_storage

    payload = _document_dict(row, account.account_no)
    payload["url"] = document_store.download_url(row.document_id)
    payload["expires_in_seconds"] = document_storage.url_ttl_seconds()
    return payload


def document_content(actor: Any, account_id: Any, document_id: Any, mode: str) -> dict[str, Any]:
    """The bytes of one filed document, for `GET …/documents/{docId}/content`.

    `DEF-CUS-9147`: a clerk could FILE a document on an account and not OPEN it —
    the tab's row carried a bin and nothing else, while `document_link` above
    had been served since wave I and called by no screen (hard-won law 2's
    mirror). The service request's documents met the same gap first and were
    given this route by `CR-158-BRC10`; this is THAT route for an account, not a
    second design: same modes, same inline list, same headers in the view, same
    audit verbs one entity over.

    ⚠ **WHY NOT THE BEARER LINK ABOVE.** It works only where the store mints an
    `https:` URL — the filesystem backend mints `file://`, which a browser
    refuses — and a bare object-store link carries none of the headers the view
    sets (`Content-Disposition`, `nosniff`, a script-forbidding policy). The
    link stays for any caller that wants one.

    Resolved under THIS tenant first (`_account_or_404`, `_live_filing`): another
    utility asking gets the 404 a missing document gets, and a WITHDRAWN filing
    (`BR-CUS-1052`) is not openable here either. Every call writes `audit_log`.
    """
    from apps.customers.service_request_documents import (
        CONTENT_MODES,
        CONTENT_VIEW,
        INLINE_CONTENT_TYPES,
    )

    if mode not in CONTENT_MODES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.documentModeUnknown",
            br_ref="DEF-CUS-9147",
            params={"value": str(mode)},
        )
    account = _account_or_404(account_id)
    row = _live_filing(account, document_id)
    reference = document_store.reference(row.document_id)
    payload = document_store.fetch(row.document_id)
    content_type = (reference.content_type or "").split(";")[0].strip().lower()
    inline = mode == CONTENT_VIEW and content_type in INLINE_CONTENT_TYPES
    core_audit.write_row(
        action=(
            "customers.account_document.viewed"
            if mode == CONTENT_VIEW
            else "customers.account_document.downloaded"
        ),
        entity_type="account_document",
        entity_id=row.id,
        actor_user_id=_actor_id(actor),
        after={
            "account_id": str(account.pk),
            "document_id": str(row.document_id),
            "content_type": content_type,
            "bytes": len(payload),
        },
    )
    return {
        "payload": payload,
        "content_type": content_type if content_type in ALLOWED_CONTENT_TYPES else "application/octet-stream",
        "name": _visible_name(row.document.display_name, account.account_no) or "document",
        "inline": inline,
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE WRITE
# ═══════════════════════════════════════════════════════════════════════════



def checked_file(payload: dict[str, Any], upload: Any) -> tuple[str, str, bytes]:
    """The name, the media type and the bytes of an upload — or its refusal.

    ⚠ **ONE GUARD FOR EVERY ACCOUNT-DOCUMENT UPLOAD (`CR-171-BRC10` P2.25).**
    Lifted out of :func:`file_document` unchanged so the move-in wizard's
    *stage now, file at Complete* (`move_in_documents.stage`) refuses exactly
    what this door refuses — `BR-SHL-031`'s allowlist (415) and 10 MB cap (413),
    a missing name and an empty file — with no second copy to drift.
    """
    name = str(payload.get("name") or getattr(upload, "name", "") or "").strip()
    if not name:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.document.name_required",
            br_ref="BR-CUS-036",
        )

    content_type = str(
        payload.get("content_type") or getattr(upload, "content_type", "") or ""
    ).strip().lower()
    # ⚠ `image/jpeg; charset=binary` is a legal header. Compare the media type,
    # never the whole header, or a browser that adds a parameter gets a 415 for
    # a file that is on the list.
    media_type = content_type.split(";")[0].strip()
    if media_type not in ALLOWED_CONTENT_TYPES:
        # 415 — 11b G11, `BR-SHL-031`'s allowlist.
        raise UploadRefused(
            415,
            "customers.document.type_not_allowed",
            br_ref="BR-SHL-031",
            content_type=media_type or "unknown",
            allowed=", ".join(ALLOWED_EXTENSIONS),
        )

    payload_bytes = upload.read() if hasattr(upload, "read") else bytes(upload or b"")
    if not payload_bytes:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.document.file_required",
            br_ref="BR-SHL-031",
        )
    if len(payload_bytes) > MAX_UPLOAD_BYTES:
        # 413 — 11b G11, `BR-SHL-031`'s 10 MB cap.
        raise UploadRefused(
            413,
            "customers.document.too_large",
            br_ref="BR-SHL-031",
            bytes=str(len(payload_bytes)),
            max_mb=str(MAX_UPLOAD_BYTES // (1024 * 1024)),
        )
    return name, media_type, payload_bytes


def file_document(actor: Any, account_id: Any, payload: dict[str, Any], upload: Any) -> dict:
    """`POST /accounts/{id}/documents` — the bytes and the filing card.

    ⚠ **THE FILING CARD'S ID IS MINTED HERE, BEFORE THE DOCUMENT, AND IT IS THE
    DOCUMENT'S `source_id`.** `uq_stored_documents_filed` allows one artefact per
    `(tenant, source_type, source_id, content_type)`, so under
    `SOURCE_CUSTOMER_ACCOUNT` the SECOND `application/pdf` on one account is
    refused by the database. That constraint is right and is not widened here —
    its reasoning is about RENDERINGS of one document, and a lease and a
    driver's licence are not two renderings of an account. `tenancy/0044` is the
    ninth source type this needs, and `tenancy/0040` is the same finding for a
    technician's ninth photograph.

    ⚠ **BYTES FIRST, THEN THE ROW**, mirroring `document_store.store()` and
    `work.evidence.record_attachment`. The document row cannot be deleted (the
    write-once trigger), so writing the card first and failing the upload would
    leave a filing card pointing at nothing — and nothing could remove it.

    ⚠ **THE CARD IS WRITTEN INSIDE A SAVEPOINT — hard-won law 14.** On
    PostgreSQL a failed statement poisons the whole transaction, so a caller
    that catches an `IntegrityError` here without a nested `transaction.atomic()`
    would raise `InFailedSqlTransaction` on its very next query. **SQLite has no
    aborted-transaction state and `config/settings/test.py` hardcodes SQLite**,
    so the version without the savepoint passes the entire suite green. Do not
    simplify it away.
    """
    account = _account_or_404(account_id)

    doc_type = str(payload.get("doc_type") or "").strip().lower()
    if doc_type not in DOCUMENT_TYPES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.document.type_unknown",
            br_ref="BR-CUS-036",
            params={"type": doc_type, "allowed": ", ".join(DOCUMENT_TYPES)},
        )
    if doc_type not in UPLOADABLE_TYPES:
        # `BR-CUS-036`: system documents *"attach automatically"*. A person
        # typing `system` would make "the product generated this" a claim a
        # person can make, which is the one thing the word means.
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.document.type_not_uploadable",
            br_ref="BR-CUS-036",
            params={"type": doc_type, "allowed": ", ".join(UPLOADABLE_TYPES)},
        )

    name, media_type, payload_bytes = checked_file(payload, upload)

    card_id = uuid7()
    moment = timezone.now()

    # ⚠ **THE DISPLAY NAME IS COMPOSED HERE AND NOWHERE ELSE, BECAUSE ONLY
    # CUSTOMERS CAN.** `document_store._require_display_name` refuses to invent
    # one and says why: a usable name needs the account number, which lives in
    # this module. The shape mirrors the storage key so an unpacked export reads
    # like the bucket — `<kind>/<yyyy>/<mm>/<human reference>`.
    account_no = (getattr(account, "account_no", "") or str(account.pk)).strip()
    safe = name.replace("/", "-").replace("\\", "-").lstrip(".")
    display_name = f"account-documents/{moment:%Y}/{moment:%m}/{account_no}-{safe}"

    ref = document_store.store(
        kind=KIND_ACCOUNT_DOCUMENT,
        source_type=SOURCE_ACCOUNT_DOCUMENT,
        source_id=card_id,
        content_type=media_type,
        display_name=display_name,
        payload=payload_bytes,
        actor_user_id=_actor_id(actor),
        process=None if _actor_id(actor) else "customers.account_documents",
    )

    # ⚠ A SAVEPOINT, NOT A CONVENIENCE — hard-won law 14. See the docstring.
    with transaction.atomic():
        row = AccountDocument.objects.create(
            id=card_id,
            tenant_id=account.tenant_id,
            account_id=account.pk,
            document_id=ref.id,
            doc_type=doc_type,
            uploaded_by_id=_actor_id(actor),
            uploaded_by_process=None if _actor_id(actor) else "customers.account_documents",
            uploaded_at=moment,
        )

    # Hard rule 7 covers MONEY actions and filing a document is not one. A row
    # is written anyway, and the module's model docstring argues why: a document
    # filed against a financial record is evidence about that record, and the
    # store's own `document.stored` row cannot name the ACCOUNT — it does not
    # know what an account is.
    core_audit.write_row(
        action="customers.account_document.filed",
        entity_type="account_document",
        entity_id=row.id,
        actor_user_id=_actor_id(actor),
        after={
            "account_id": str(account.pk),
            "doc_type": doc_type,
            "document_id": str(ref.id),
            "display_name": display_name,
            "byte_length": len(payload_bytes),
            "content_type": media_type,
        },
    )

    # The POST answers with the SAME shape the list serves, `account_no` and
    # all — a create whose `name` differs from the row the list then draws is
    # two answers to one question.
    return _document_dict(
        AccountDocument.objects.select_related("document", "uploaded_by").get(pk=row.pk),
        account_no,
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE WITHDRAWAL — `BR-CUS-1052`
# ═══════════════════════════════════════════════════════════════════════════


def withdraw_document(actor: Any, account_id: Any, document_id: Any) -> None:
    """`DELETE /accounts/{id}/documents/{docId}` — the filing leaves the account.

    **PO 2026-09-13, verbatim: *"We should have this functionality"***, on the
    wave I report that *"a clerk who files the wrong scan cannot take it back"*.
    `BR-CUS-1052` is the rule.

    ⚠ **WHAT IS REMOVED IS THE FILING. THE BYTES ARE NOT TOUCHED, AND NOTHING
    HERE COULD TOUCH THEM IF IT WANTED TO.** `BR-SHL-031` makes the legal class
    write-once for seven years, `tenancy/0026` enforces it with a database
    trigger, `NFR-35` says the same — **none of that is reversed by this ruling
    and nothing in this function tries.** No call is made into
    `document_store`, no `StoredDocument` row is read or written, and the object
    stays under its retention lock. After this runs, the document is not listed,
    not counted and not openable on this account; it is not erased anywhere.

    ⚠ **A `DELETE` VERB OVER AN UPDATE, AND THE HONESTY IS AT THE RIGHT
    LAYER.** What the address `/accounts/{id}/documents/{docId}` names is *this
    account's filing of that document*, and that is exactly what stops existing:
    the very next `GET` of the same address answers 404. The verb describes the
    RESOURCE the caller addressed, not the bytes two tables away — and the two
    honest sentences about the bytes live in the dialog the clerk reads and in
    `BR-CUS-1052`, not in an HTTP method name.

    ⚠ **AUDIT-LOCKED TYPES REFUSE BY NAME — `BR-CUS-036`, and the refusal is a
    409 rather than a 404.** A contract the system attached is not hidden from
    the clerk and not silently un-removable: `BIZ-LOCKED` carries the reason,
    and `BR-SHL-025` puts that same reason on the disabled control before the
    clerk ever presses it. The one thing this must NOT do is answer *"no such
    document"*, which would teach a clerk that the row had gone when it had not.

    ⚠ **THE ACTOR IS RESOLVED AND CHECKED BEFORE THE WRITE — hard-won law 14.**
    `ck_account_documents_withdrawal` would catch an anonymous withdrawal at the
    database, and on PostgreSQL that refusal poisons the whole transaction while
    on SQLite — which `config/settings/test.py` hardcodes — there is no such
    state at all. So the constraint is the backstop and this guard is the
    mechanism, which is the only arrangement that behaves the same on both.

    ⚠ **NOTHING PUTS IT BACK, AND THAT IS A RECORDED JUDGMENT.** No rule says
    whether a withdrawn filing is reachable again, so the narrower thing is
    built: gone from the clerk's view, recoverable only by somebody with the
    audit trail (decision log, 2026-09-13). A restore endpoint is a second
    decision and it is unmade — do not add one here without a ruling.
    """
    account = _account_or_404(account_id)
    row = _live_filing(account, document_id)

    if row.doc_type not in WITHDRAWABLE_TYPES:
        # `BR-CUS-036`: *"system/contract docs audit-locked (IS-1 🔒)"*. 409,
        # not 404 — the row is there and the clerk may not take it back, which
        # is a different fact from "there is nothing here".
        raise errors.BizError(
            errors.BIZ_LOCKED,
            message_key="customers.document.withdraw_locked",
            br_ref="BR-CUS-036",
            params={"type": row.doc_type},
        )

    who = core_audit.actor_user_id(actor)
    if who is None:
        # No automation withdraws anything (see `withdrawn_by`'s note). An
        # unresolvable actor reaching here is a caller that skipped the
        # endpoint, and *"nobody knows"* is not an answer a filing cabinet may
        # give — the same line `ck_account_documents_actor` holds for filing.
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.document.withdraw_actor_required",
            br_ref="BR-CUS-1052",
        )

    moment = timezone.now()
    # ⚠ **THE UPDATE IS SCOPED BY `withdrawn_at__isnull=True` A SECOND TIME**,
    # so two clerks pressing Remove on the same row in the same second write it
    # once: the second `UPDATE` matches zero rows and changes nothing. It costs
    # one clause and removes the only race this function has.
    changed = AccountDocument.objects.filter(
        pk=row.pk, tenant_id=account.tenant_id, withdrawn_at__isnull=True
    ).update(withdrawn_at=moment, withdrawn_by_id=who)
    if changed == 0:
        # Somebody else withdrew it between the read and the write. The account
        # does not hold it, which is the same answer the read gives.
        raise errors.deny_as_not_found("BR-TEN-003")

    # `BR-CUS-1052`: *"the withdrawal writes an audit row naming who did it and
    # when"*. Hard rule 7 covers MONEY actions and this is not one — the same
    # argument the filing row makes in this module's model docstring applies
    # again, one step stronger: a document leaving a customer's file is exactly
    # the event somebody later asks about, and after this row the OLD state
    # lives nowhere else.
    #
    # ⚠ **`before` CARRIES WHAT THE ACCOUNT HAS STOPPED HOLDING**, including the
    # `document_id`, because that id is the only way back to the object still
    # sitting under its retention lock. `after` carries the withdrawal itself.
    core_audit.write_row(
        action="customers.account_document.withdrawn",
        entity_type="account_document",
        entity_id=row.id,
        actor_user_id=who,
        before={
            "account_id": str(account.pk),
            "doc_type": row.doc_type,
            "document_id": str(row.document_id),
            "display_name": row.document.display_name,
            "uploaded_at": row.uploaded_at.isoformat(),
        },
        after={"withdrawn_at": moment.isoformat(), "withdrawn_by": str(who)},
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-094-BRC01 wave I (sources: 04-docs/05-modules/03-customers/02-business-rules.md BR-CUS-036 · 04-docs/05-modules/00-platform-shell/02-business-rules.md BR-SHL-031 · 04-docs/01-spec/11b-api-audit.md §S21 + G11 · 04-docs/05-modules/03-customers/conformance/CR-094-lane2-account-detail-step1.md F10 + §1.5 ACC-T10 · 06-backend/apps/tenancy/document_store.py · 06-backend/apps/work/evidence.py, the worked precedent)
# generated: 2026-09-12 by the CR-094-BRC01 wave I lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — the RLS migration is 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: RED PROVED FIRST — see the lane report and tests/test_cr094_i_account_documents.py.
# exceptions: (1) NO VIRUS SCAN, BY PO RULING OF 2026-09-22 AND 2026-09-23 — `BR-SHL-253`'s wire scanner (2026-09-13) was removed with its middleware and settings (`DEF-SHL-6347`); the allowlist and the cap are the whole upload guard and neither is a scan. (2) THE 10 MB CAP IS A CONSTANT, not per-tenant: the rule says "10MB tenant-config" and no settings family declares the key; inventing one is how two spellings of one option appear. (3) NO DELETE, no endpoint and no column — `BR-CUS-036` audit-locks system/contract, `NFR-35` makes the bytes write-once for seven years, and `ACC-T10` draws no row action. (4) The drawing's `Evidence` filter chip is NOT built: it is not one of `BR-CUS-036`'s five CONFIRMED types and a wireframe cannot amend signed law — FILED, decision log 2026-09-12.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

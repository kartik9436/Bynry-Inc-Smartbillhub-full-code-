# ── Trace ──────────────────────────────────────────────
# Change:   CR-049 task 1 — the document store's published service. This is the
#           callable billing, notifications, customers, ledger, metering and
#           payments use; none of them touches the table or the bucket.
# Rules:    BR-NOT-027 (a sent legal document is frozen AS THE DOCUMENT, and a
#           reprint serves THAT — never a fresh render) · BR-NOT-025 (the
#           pinned template version is PROVENANCE; this is the document) ·
#           BR-TEN-031 (the owning module publishes the callable its
#           neighbours use) · NFR-33 · NFR-35 (write-once, 7 years) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 4 (immutability) ·
#           rule 7 (audit) · B2 §2 (cross-module writes are forbidden) ·
#           hard-won law 1 (a comment claiming a guarantee is not the
#           guarantee)
# Tests:    06-backend/tests/test_cr049_t1_document_store.py
# Impacts:  CR-049 task 2 calls `store()` from the dispatcher · task 3 calls
#           `for_source()` and `download_url()` for a reprint · task 4 calls
#           `store()` at bill issue · the bulk export calls `manifest()`.
#           NONE of them is built here.
# ───────────────────────────────────────────────────────
"""Store a frozen document, and get it back — the only door into either half.

Everything above this file talks to these functions and to nothing else. It
resolves the row (RLS-scoped) and then, and only then, the bytes. Nothing
outside this module may import `document_storage`, and nothing outside tenancy
may touch `StoredDocument` — B2 §2's ban on cross-module writes, honoured by
publishing a callable rather than by hoping.

⚠ THE BYTES ARE WRITTEN BEFORE THE ROW, AND THE ORDER IS DELIBERATE
--------------------------------------------------------------------
The obvious order is row-then-bytes, so a failed upload rolls back. **It is the
wrong way round here**, because `stored_documents` has a write-once trigger:
a row whose upload then failed **can never be deleted**, and this product would
carry a permanent record of a document that does not exist. Every reprint of it
would answer *"stored"* and then fail to produce anything.

Written bytes-first, the failure mode is an object in the bucket that no row
names. That is **invisible and harmless**: nothing lists the bucket (see
`document_storage`), so nothing will ever find it, and a lifecycle rule sweeps
it. Trading a permanent lie for an invisible orphan is not a close call.

⚠ "NONE STORED" IS NOT THE SAME AS "WE DID NOT LOOK"
------------------------------------------------------
`for_source()` returns a `DocumentLookup` which is **never ambiguous**: either
`document` is set, or `unavailable_reason` says `document_not_stored`. It can
never return an empty-looking success, because that is precisely how a caller
ends up rendering a fresh document as though it were the original — the failure
`BR-NOT-027` exists to prevent, one layer up.

This is the discipline `apps/billing/release.py` already states of a different
count: *"'0 of 1,122 hold an address' and 'we could not count' must never
render the same"*, and the one `import_rules.unavailable_reason` follows.

**There is deliberately no "we did not look" value in this module**, and the
reason is structural rather than an omission: `for_source()` always looks. The
honest-state requirement — a message that reached `sent` with no artefact must
be served as *re-rendered from data, not the original* — is `CR-049` task 7,
and it is written on top of `document_not_stored`, not instead of it.

⚠ A CALLER IN TENANT A ASKING FOR TENANT B'S DOCUMENT GETS `document_not_stored`
--------------------------------------------------------------------------------
The same answer as one asking about a bill that never existed. **Existence must
not leak (HR-1)**, and nothing here has to remember that: the read is an
ordinary RLS-scoped query, so tenant B's row is not merely hidden from the
answer — it is not in the result set the answer is computed from.

⚠ ENUMERATION IS ALWAYS A DATABASE QUERY. NEVER A BUCKET LISTING.
-------------------------------------------------------------------
`manifest()` and `list_for_kind()` read `stored_documents` over the
`(tenant, stored_at)` and `(tenant, kind, stored_at)` indexes.
`document_storage` has no `list()` and must never grow one.

**Two reasons, and the second is the one people forget.** A bucket listing is
slow at half a million objects and pages badly. And a bucket listing is
**scoped by prefix, which is a string** — one wrong prefix, or one caller
passing a tenant id it was given, and the listing crosses tenants silently. The
database cannot make that mistake: the policy is evaluated per row.

**And this is what makes the bulk export the PO asked for possible, not what
blocks it.** A listing returns keys and byte counts. This table returns *the
March bill for account ACC-1042, 61 KB of PDF, hashed to abc…* — which is the
difference between an export a utility can use and a folder of UUIDs. The
arithmetic (532,000 documents, 4.4 hours serial versus 2.7 minutes in parallel)
is in `document_models.py`.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Iterable
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.tenancy import document_storage
from apps.tenancy.document_models import (
    CHANNELS,
    DOCUMENT_KINDS,
    SOURCE_TYPES,
    StoredDocument,
    module_for_kind,
)
from apps.tenancy.models import Tenant
from core import audit as core_audit
from core.dbfields import uuid7
from core.tenancy import current_tenant_id

# ═══════════════════════════════════════════════════════════════════════════
# WHY A LOOKUP CAME BACK EMPTY — codes, never prose
# ═══════════════════════════════════════════════════════════════════════════
# A screen groups on these and a screen cannot group on a sentence, which is
# the rule `apps/notifications/provider_seam.py` states for its own refusals.

#: We looked, in this tenant, and there is no frozen artefact for that source.
#: **This is also the answer a caller in tenant A gets for tenant B's document**
#: — deliberately indistinguishable, because existence must not leak.
DOCUMENT_NOT_STORED = "document_not_stored"

#: The row is there and the bytes are not — the object was written and has since
#: been removed. NOT the same as `DOCUMENT_NOT_STORED`, and never rendered as
#: it: one means no document was produced, the other means one was produced and
#: this product can no longer show it, which is a far worse thing to discover
#: and a far worse thing to hide.
DOCUMENT_BYTES_MISSING = "document_bytes_missing"

#: The bytes came back and do not hash to what the row recorded. Decision 7's
#: whole purpose.
DOCUMENT_HASH_MISMATCH = "document_hash_mismatch"

#: The longest a human name may be. Not a database limit — the column is TEXT —
#: but a filename limit: an export unpacks these onto a filesystem, and most
#: refuse a path segment over 255 bytes.
MAX_DISPLAY_NAME = 255


class DocumentStoreError(RuntimeError):
    """A caller asked this module to do something it may not do."""


# ═══════════════════════════════════════════════════════════════════════════
# WHAT A CALLER GETS BACK
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class StoredDocumentRef:
    """One frozen document, as everything outside tenancy sees it.

    ⚠ **THERE IS NO `storage_key` ON THIS DATACLASS, AND THAT IS THE DESIGN.**
    A key is how this module finds bytes; handing it out would let a caller ask
    for a key it composed, which is the one thing `document_storage` says must
    never happen. A caller that wants the bytes calls `fetch()`; a caller that
    wants to give somebody a link calls `download_url()`. Both take an `id`
    they got from here, and both re-resolve the row under RLS.
    """

    id: UUID
    kind: str
    source_type: str
    source_id: UUID
    channel: str | None
    display_name: str
    content_hash: str
    byte_length: int
    content_type: str
    stored_at: dt.datetime
    storage_backend: str


@dataclass(frozen=True)
class DocumentLookup:
    """The answer to *"is there a frozen document for this?"* — never ambiguous.

    Exactly one of the two is set. A caller that reads `document` without
    checking gets `None` and a reason it can print; a caller that wants the
    reason has it without inferring one from an empty result.
    """

    document: StoredDocumentRef | None = None
    unavailable_reason: str | None = None

    @property
    def found(self) -> bool:
        return self.document is not None


def _ref(row: StoredDocument) -> StoredDocumentRef:
    return StoredDocumentRef(
        id=row.id,
        kind=row.kind,
        source_type=row.source_type,
        source_id=row.source_id,
        channel=row.channel,
        display_name=row.display_name,
        content_hash=row.content_hash,
        byte_length=row.byte_length,
        content_type=row.content_type,
        stored_at=row.stored_at,
        storage_backend=row.storage_backend,
    )


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATION — refuse at the door, in words
# ═══════════════════════════════════════════════════════════════════════════


def _require_display_name(name: str) -> str:
    """The human name, checked and never invented.

    **This module does not compose a fallback**, and that is the decision
    recorded in `document_models.py`: a usable name needs the account number
    and the invoice number, which live in `customers` and `billing`, and
    reading them here is the cross-module read B2 §2 forbids. So the writer
    supplies it and this refuses if it did not.

    An invented fallback would be worse than a refusal. `document-0198f3c2…` in
    an export of 532,000 files is indistinguishable from a name somebody meant,
    so the utility would discover the problem after unpacking the archive
    rather than when the document was stored.
    """
    name = (name or "").strip()
    if not name:
        raise DocumentStoreError(
            "a stored document needs a display_name — the human name an export "
            "unpacks to, e.g. 'bills/2026/03/ACC-1042-INV-000123.pdf'. The store "
            "cannot compose one: a usable name needs the account and invoice numbers, "
            "which belong to customers and billing, and reading them from here is the "
            "cross-module read B2 §2 forbids."
        )
    if len(name) > MAX_DISPLAY_NAME:
        raise DocumentStoreError(
            f"display_name is {len(name)} characters; the limit is {MAX_DISPLAY_NAME}, "
            "because an export unpacks these onto a filesystem and most refuse a longer "
            "path segment."
        )
    if name.startswith("/") or ".." in name or "\\" in name:
        raise DocumentStoreError(
            f"display_name {name!r} is not a safe relative path. An export unpacks "
            "these into a directory, so a leading slash or '..' would write outside it."
        )
    return name


def _require_choice(value: Any, allowed: Iterable[str], field: str) -> str:
    if value not in allowed:
        raise DocumentStoreError(
            f"{field}={value!r} is not one this store knows. The permitted set is "
            f"{sorted(allowed)}, and it is a CHECK constraint as well as this line: a "
            "kind nobody has ruled on is how a document store becomes a junk drawer "
            "with no answer to 'is this the letter?'. Adding one is a migration and a "
            "decision-log row."
        )
    return str(value)


def _tenant_now() -> UUID:
    tenant_id = current_tenant_id()
    if tenant_id is None:
        raise DocumentStoreError(
            "no tenant context is set, so this call cannot name whose document it is "
            "(CLAUDE.md hard rule 1). Enter core.tenancy.tenant_context(...) first; the "
            "database would refuse the row anyway, and refusing here says why."
        )
    return tenant_id


def _tenant_folder(tenant_id: UUID) -> str:
    """The utility's web name (`tenants.subdomain`) — the first folder of its keys.

    `CR-160-BRC10` (PO 2026-10-02, *"Yes, web name"*). Read HERE, server-side,
    for the tenant the session context already names — never passed in, so no
    caller can write into another utility's folder. `tenants` is the platform
    root and carries no tenant policy (B2 §3), so this read sees exactly one
    row: the session's own.

    ⚠ The web name is set once at sign-up and no product path changes it — but
    nothing in the database forbids it. If an operator ever renames one, files
    written before stay under the OLD folder: still readable, because each row
    stores its exact key, and missed by any whole-utility prefix operation
    (decision log 2026-10-02).
    """
    folder = Tenant.objects.filter(id=tenant_id).values_list("subdomain", flat=True).first()
    if not folder:
        raise DocumentStoreError(
            "the session's utility has no web name, so its documents have no folder "
            "to go in (CR-160-BRC10)."
        )
    return folder


# ═══════════════════════════════════════════════════════════════════════════
# THE WRITE
# ═══════════════════════════════════════════════════════════════════════════


def store(
    *,
    kind: str,
    source_type: str,
    source_id: UUID | str,
    content_type: str,
    display_name: str,
    payload: bytes,
    channel: str | None = None,
    actor_user_id: UUID | str | None = None,
    process: str | None = None,
) -> StoredDocumentRef:
    """Freeze one document: put the bytes away, then record that they exist.

    The tenant is **never a parameter** — it is taken from the session context
    the request or the job already set. A tenant argument would be a way to
    write into another tenant, and `document_storage` says the same thing about
    keys for the same reason.

    `channel` is `None` when the document is stored at CREATION rather than at
    SEND: a bill frozen at issue, an agreement that is filed rather than
    posted. A document that WAS sent always carries the channel it went on.

    `actor_user_id` or `process` — at least one. A bill run has no user and a
    person uploading a certificate has no job, and *"nobody knows"* is not one
    of the answers a legal document may give.

    ⚠ **BYTES FIRST, THEN THE ROW** — the module docstring argues it. Do not
    "fix" this by wrapping the upload in the transaction: the row cannot be
    deleted afterwards, so a failed upload would leave a permanent record of a
    document that does not exist.
    """
    tenant_id = _tenant_now()
    kind = _require_choice(kind, DOCUMENT_KINDS, "kind")
    source_type = _require_choice(source_type, SOURCE_TYPES, "source_type")
    if channel is not None:
        channel = _require_choice(channel, CHANNELS, "channel")
    display_name = _require_display_name(display_name)
    if not payload:
        raise DocumentStoreError(
            "refusing to store an empty document. Zero bytes is the shape a failed "
            "render takes, and storing one would make 'the letter exists' true about an "
            "empty file."
        )
    if not (content_type or "").strip():
        raise DocumentStoreError(
            "a stored document needs a content_type — a reader has to know whether it "
            "is holding a PDF or an HTML page, and the object store will not guess."
        )
    if actor_user_id is None and not (process or "").strip():
        raise DocumentStoreError(
            "a stored document needs an author: an actor_user_id, or a process such as "
            "'notifications.dispatcher'. A legal document whose origin is unrecorded is "
            "unprovable, which is the opposite of what freezing it is for."
        )

    document_id = uuid7()
    moment = timezone.now()
    hex_digest = document_storage.content_hash(payload)
    # CR-160-BRC10: `t/<web name>/<module>/<yyyy>/<mm>/<id>[.ext]` — every part
    # from THIS row: its tenant's web name, its kind's module, its own id.
    key = document_storage.key_for(
        tenant_folder=_tenant_folder(tenant_id),
        module=module_for_kind(kind),
        document_id=document_id,
        moment=moment,
        extension=document_storage.extension_for(content_type),
    )

    backend = document_storage.backend()
    backend.put(
        key=key,
        payload=payload,
        content_type=content_type,
        hex_digest=hex_digest,
        retain_for_years=document_storage.retention_years(),
    )

    with transaction.atomic():
        row = StoredDocument(
            id=document_id,
            tenant_id=tenant_id,
            kind=kind,
            source_type=source_type,
            source_id=_as_uuid(source_id),
            channel=channel,
            storage_key=key,
            storage_backend=backend.name,
            content_hash=hex_digest,
            byte_length=len(payload),
            content_type=content_type,
            display_name=display_name,
            stored_by_user_id=_as_uuid(actor_user_id) if actor_user_id else None,
            stored_by_process=(process or "").strip() or None,
        )
        row.save()

    # Hard rule 7 is about money actions; this is not one. It gets a row anyway,
    # because "who froze this document, and when" is exactly the question a
    # regulator asks after they have seen the document itself, and the row is
    # the only place that answer survives the seven years.
    core_audit.write_row(
        action="document.stored",
        entity_type="stored_document",
        entity_id=document_id,
        actor_user_id=actor_user_id,
        after={
            "kind": kind,
            "source_type": source_type,
            "source_id": str(source_id),
            "channel": channel,
            "display_name": display_name,
            "content_hash": hex_digest,
            "byte_length": len(payload),
            "content_type": content_type,
            "storage_backend": backend.name,
            "process": process,
        },
    )
    return _ref(row)


def _as_uuid(value: UUID | str | None) -> UUID | None:
    if value is None:
        return None
    return value if isinstance(value, UUID) else UUID(str(value))


# ═══════════════════════════════════════════════════════════════════════════
# THE READ
# ═══════════════════════════════════════════════════════════════════════════


def for_source(
    *,
    source_type: str,
    source_id: UUID | str,
    channel: str | None = None,
    content_type: str | None = None,
) -> DocumentLookup:
    """The frozen document for one source — or a plain statement that there is none.

    ⚠ **NEVER RETURNS AN EMPTY SUCCESS.** Either `document` is set or
    `unavailable_reason` is `document_not_stored`. A caller cannot mistake
    absence for a document, which is the whole reason this returns a wrapper
    instead of `StoredDocumentRef | None`.

    ⚠ A caller in another tenant gets `document_not_stored` — the same answer
    as for a source that never existed. Nothing here implements that: the
    queryset is RLS-scoped, so the other tenant's row is not in the set the
    answer is computed from.

    `channel` and `content_type` narrow it, because one bill can hold a PDF and
    an HTML and one message can have gone out on two channels. Left off, the
    NEWEST matching document is returned — and if a caller is choosing between
    several, that is a sign it should have said which one it meant.
    """
    # ⚠ SCOPED IN THE APP LAYER **AND** BY RLS — two guarantees, not a habit.
    # G5 makes both promises separately: every selector filters by the caller's
    # tenant (provable on any vendor), and the DATABASE refuses a foreign row
    # even when that filter is wrong (provable only on PostgreSQL, under a role
    # RLS applies to). Relying on RLS alone would make this correct in
    # production and WRONG on the sqlite database the suite runs on — and a
    # guarantee that holds only where nobody tests it is hard-won law 1's
    # shape. It is also wrong on any cluster whose app role is a superuser,
    # which the development cluster's is.
    tenant_id = _tenant_now()
    query = StoredDocument.objects.filter(
        tenant_id=tenant_id, source_type=source_type, source_id=_as_uuid(source_id)
    )
    if channel is not None:
        query = query.filter(channel=channel)
    if content_type is not None:
        query = query.filter(content_type=content_type)
    row = query.order_by("-stored_at").first()
    if row is None:
        return DocumentLookup(unavailable_reason=DOCUMENT_NOT_STORED)
    return DocumentLookup(document=_ref(row))


def _resolve(document_id: UUID | str) -> StoredDocument:
    """The row, RLS-scoped — the ONLY way this module ever learns a storage key.

    ⚠ This is decision 4 in one function. `document_storage.key_for` composes a
    key from a row; every read composes nothing and reads the key out of the
    row it just resolved under the caller's own tenant context. There is no
    path anywhere in this product from a caller-supplied string to a bucket
    object.
    """
    tenant_id = _tenant_now()
    row = StoredDocument.objects.filter(tenant_id=tenant_id, id=_as_uuid(document_id)).first()
    if row is None:
        raise DocumentStoreError(
            f"no stored document {document_id} — either it does not exist or it belongs "
            "to another tenant, and those are deliberately the same answer (HR-1: "
            "existence must not leak)."
        )
    return row


def reference(document_id: UUID | str) -> StoredDocumentRef:
    """One document's RECORD by its own id — the metadata, without the bytes.

    Added for `CR-049` task 3: a reprint route needs to answer *"what is this
    document"* (kind, human name, hash, size, when it was sealed) separately
    from *"give me its contents"*, because the two have different costs and the
    register lists five hundred of the first for every one of the second.

    ⚠ **THE SAME 404 FOR ABSENT AND FOR ANOTHER TENANT'S.** This is `_resolve`
    with the row shaped for a caller, so it inherits the RLS-scoped query
    unchanged: a foreign row is not hidden from the answer, it is not in the set
    the answer is computed from. It raises `DocumentStoreError` for both, and a
    caller that could tell them apart would eventually report the difference
    (HR-1).

    ⚠ **STILL NO `storage_key`** — `StoredDocumentRef` does not carry one, which
    is decision 4. A caller wanting bytes calls `fetch()`; a caller wanting a
    link calls `download_url()`. Both re-resolve the row themselves.
    """
    return _ref(_resolve(document_id))


def fetch(document_id: UUID | str) -> bytes:
    """The exact bytes that were stored — verified, or refused.

    ⚠ **THE HASH IS RE-COMPUTED ON EVERY READ AND COMPARED (decision 7).** A
    hash written down and never checked prevents nothing; this is the check.
    The cloud's own checksum guards the upload and the transfer, and this
    guards everything after — including the case that matters most, which is a
    document quietly replaced years later.
    """
    row = _resolve(document_id)
    backend = document_storage.backend()
    if backend.name != row.storage_backend:
        raise DocumentStoreError(
            f"document {row.id} was stored on the {row.storage_backend!r} backend and "
            f"this deployment is configured for {backend.name!r}. The bytes are where "
            "they were put; switching backends does not move them, and guessing which "
            "one to ask would be a 404 dressed up as an answer."
        )
    payload = backend.get(key=row.storage_key)
    actual = document_storage.content_hash(payload)
    if actual != row.content_hash:
        raise document_storage.ContentHashMismatch(
            f"document {row.id} ({row.display_name}) hashed to {actual} and the record "
            f"says {row.content_hash}. The bytes in the store are NOT the bytes that "
            "were frozen. Nothing may serve this as the document the customer received."
        )
    return payload


def download_url(document_id: UUID | str) -> str:
    """A temporary link to one document, issued only after the row resolved.

    The row is resolved under the caller's tenant context FIRST — so a link is
    never issued for a document the caller could not have found — and only then
    is a URL minted for the key that row carries.

    ⚠ **FOUR HOURS, AND IT IS A BEARER TOKEN** (PO ruling 2026-08-30). Whoever
    holds this URL reads this document, with no session and no further check,
    until it expires. The exposure is bounded to this one document and cannot
    be used to find another. Do not put one in an email that outlives it, and
    do not lengthen the TTL — issue a new link instead.
    """
    row = _resolve(document_id)
    backend = document_storage.backend()
    return backend.temporary_read_url(
        key=row.storage_key, expires_in=document_storage.url_ttl_seconds()
    )


def list_for_kind(*, kind: str, limit: int = 100) -> list[StoredDocumentRef]:
    """This tenant's documents of one kind, newest first — a DATABASE query.

    Over `ix_stored_docs_kind` (`tenant, kind, stored_at`). Never a bucket
    listing; the module docstring gives both reasons.
    """
    rows = StoredDocument.objects.filter(tenant_id=_tenant_now(), kind=kind).order_by("-stored_at")[
        :limit
    ]
    return [_ref(row) for row in rows]


def manifest(
    *,
    since: dt.datetime | None = None,
    until: dt.datetime | None = None,
    limit: int | None = None,
) -> list[StoredDocumentRef]:
    """Every document this tenant holds, newest first — the export's enumeration.

    ⚠ **THIS IS NOT THE BULK EXPORT.** The export is its own task in `CR-049`
    and another lane's; this is the enumeration it will read, put here because
    the index it needs was cheap in the table today and a migration later.

    Over `ix_stored_docs_all` (`tenant, stored_at`), and the number is the
    argument: a 3,000-connection utility seven years in holds about 532,000
    documents, which is 4.4 hours of pure latency fetched one at a time and
    about 2.7 minutes fetched a hundred at a time. **So whoever builds the
    export: enumerate here, fetch in parallel, and never proxy the bytes
    through this application** — hand out `download_url()`s and let the client
    pull them straight from the cloud. None of that is about the folder layout.
    """
    rows = StoredDocument.objects.filter(tenant_id=_tenant_now())
    if since is not None:
        rows = rows.filter(stored_at__gte=since)
    if until is not None:
        # ⚠ THE UPPER BOUND IS THE DATABASE'S JOB, NOT THE CALLER'S (CR-049 task
        # 3). A caller asking for "last July" that filtered in Python would have
        # to read every row from July to today — seven years in, that is most of
        # 532,000 rows dragged through the application to draw one table, and it
        # is the four hours step 5f says the design exists to avoid. Both bounds
        # ride the same `(tenant, stored_at)` index.
        rows = rows.filter(stored_at__lte=until)
    rows = rows.order_by("-stored_at")
    if limit is not None:
        rows = rows[:limit]
    return [_ref(row) for row in rows]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-049 task 1 (sources: 12-governance/11-change-requests.md CR-049 steps 5b/5c/5d(e) and its 2026-08-30 amendments · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-027 · NFR-33/NFR-35 · 12-governance/02-decision-log.md 2026-08-30 · 06-backend/apps/ledger/models.py ExportBatch, the worked precedent)
# generated: 2026-08-30 by the CR-049 task 1 lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — no endpoint reaches this until CR-049 task 3, and nothing WRITES into it until task 2) E=deferred(no-frontend-half — CR-049 task 3) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — a cross-tenant read was shown returning the document before RLS was applied and `document_not_stored` after; a changed byte was shown served silently before the read-time hash check and refused after. Verbatim transcripts in 06-backend/tests/test_cr049_t1_document_store.py and the lane report.
# exceptions: (1) BYTES BEFORE THE ROW, argued in the module docstring — the row cannot be deleted, so a failed upload would leave a permanent record of a document that does not exist. (2) NO `storage_key` ON THE PUBLISHED DATACLASS — a caller that could name a key could name one it composed. (3) `display_name` is REFUSED rather than defaulted; the store cannot compose one without a cross-module read. (4) An audit row is written though hard rule 7 covers money actions only — "who froze this, and when" is the question that follows "show me the document". (5) NOTHING CALLS `store()` YET; that is CR-049 task 2 and another lane's.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

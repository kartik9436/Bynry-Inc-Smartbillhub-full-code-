# ── Trace ──────────────────────────────────────────────
# Change:   CR-049 task 3 — "A reprint and a regulator request serve the stored
#           copy and never re-render". The CR marks it *"The behaviour the PO
#           actually asked for"*, and the task-2 lane's closing sentence is the
#           brief: *"no endpoint serves a frozen document yet, so a screen could
#           still re-render one and nothing I wrote would notice. The guarantee
#           is worth only what the route eventually does with it."*
# Rules:    BR-NOT-027 (a sent legal document is FROZEN AS THE DOCUMENT, and a
#           reprint serves THAT — PO 2026-08-30) · BR-NOT-025 / BR-BIL-026 (the
#           pinned version is PROVENANCE, never the rendering input) ·
#           BR-TEN-003 / HR-1 (existence must not leak) · BR-TEN-031 (the owning
#           module publishes the callable) · BR-SHL-020 (plain language when
#           something is absent) · NFR-33 · NFR-35 · CLAUDE.md rule 1 (tenant
#           scoping) · rule 7 (audit) · hard-won law 1 (a comment claiming a
#           guarantee is not the guarantee) · law 2 (built is not wired)
# Tests:    06-backend/tests/test_cr049_t3_reprint_route.py
# Impacts:  07-frontend/src/features/notifications/SettingsNotificationsTab.tsx
#           — the dispatch home's "Show me what we sent" panel, which is the
#           screen half of this task. CR-049 task 4 (the bill's stored PDF/HTML)
#           will serve through the same two document routes and needs no new
#           ones; only a bill-side lookup.
# ───────────────────────────────────────────────────────
"""Serve the letter we kept — and never, under any circumstance, make a new one.

Three routes, and the third is the regulator's:

    GET /outbound/{message_id}/document   one sent message, reproduced
    GET /documents/{document_id}          one frozen document, by its own id
    GET /documents/register               a DATE RANGE of them — the regulator
                                          request that started this CR

⚠ THE ONE THING THIS MODULE MUST NEVER DO
--------------------------------------------
**It must never render.** `apps/notifications/rendering.py` is not imported
here, and `test_cr049_t3__the_reprint_module_cannot_reach_the_renderer_at_all`
parses this file's AST to keep it that way — because "it does not call the
renderer today" is a fact about today's control flow and `BR-NOT-027` needs a
fact about the module. A lane that adds a kind-looking fallback (*"if nothing is
stored, at least show them something"*) breaks a test rather than the rule, and
the rule is the one the Product Owner actually stated:

    *"otherwie everytime we reproduce it using data in table, we might change
    something about it and that is not correct"*

⚠ THE HONEST STATE IS CARRIED ALL THE WAY TO THE SCREEN
----------------------------------------------------------
`frozen_documents.reproduce()` answers `original` or
`re_rendered_from_data_not_the_original` and never an empty success. **This
module passes that distinction through unflattened**, with the store's own code
and the i18n key the backend and the screen share, and — the part that matters —
**`document` is `null` on every non-original answer.** A screen that read
`document` without branching would print a reconstruction as the letter, which
is the defect, so there is nothing there to print.

⚠ A PRE-SIGNED URL BYPASSES THE HASH CHECK, SO THE BYTES ARE VERIFIED HERE TOO
--------------------------------------------------------------------------------
This is a judgement `CR-049` did not make for us, and it is the reason a reprint
answers with the text AND a link rather than with a link alone.

`document_store.fetch()` re-computes the content hash and refuses a mismatch
(step 5d(e) decision 7 — *"verified on read"*). **A pre-signed URL is a direct
client-to-cloud read: our code is not in that path, so nothing hashes anything.**
Handing a screen only a link would therefore have quietly retired the one check
that catches a document replaced years after it was written — the exact hazard
the decision names — while every test still passed, because the link works.

So a single-document read FETCHES (verified, refuses loudly on mismatch) and
ALSO issues the four-hour link for download. The two are not redundant: the
fetch is the guarantee, the link is the delivery. The **bulk** export is the
opposite trade and stays so — 24 GB may not be proxied through this application
(step 5f), so it hands out links and accepts that verification moves to the
consumer. One document is kilobytes; half a million is a terabyte.

⚠ NEVER A KEY, IN EITHER DIRECTION
-------------------------------------
No response carries a `storage_key`, and no request accepts one (decision 4).
A caller names a `document_id` or a `message_id`; both are resolved as RLS-scoped
rows, and the key is read out of the row that resolved. There is no path from a
string a caller composed to an object in the bucket.

⚠ CROSS-TENANT IS A 404, AND THE BODY IS THE SAME 404
--------------------------------------------------------
A caller in tenant A asking for tenant B's document gets what it would get for a
document that never existed — **byte-identical**, because a 403 is itself a
statement that the thing exists. Nothing here implements that: `selectors.
row_or_404` and `document_store`'s RLS-scoped `_resolve` both answer on an empty
result set, and `errors.NotFoundError` deliberately serialises no reason.
`test_cr049_t3__another_tenants_document_answers_EXACTLY_as_a_missing_one`
asserts the two bodies are EQUAL rather than merely both refusals.

⚠ ENUMERATION IS A DATABASE QUERY
------------------------------------
The register reads `document_store.manifest()` over the `(tenant, stored_at)`
index. It never lists the bucket — slow at half a million objects, and scoped by
a *string* prefix that one mistake turns into a cross-tenant read (step 5d).

`urlpatterns` is exported for inclusion by config/urls.py.
"""

from __future__ import annotations

import datetime as dt
from email import message_from_bytes
from email.policy import default as email_policy
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.notifications import frozen_documents, models, selectors
from apps.tenancy import document_storage, document_store
from core import audit as core_audit
from core import errors
from core.permissions import AdminOrClerk, SystemAdminOnly
from core.tenancy import require_tenant

#: The i18n keys this file's refusals carry. Named once so G18 can read the
#: catalogue and the code against each other in a single grep; a key with no
#: catalogue entry renders to a clerk as a raw dotted string.
KEY_HASH_MISMATCH = "notifications.frozenDocument.hashMismatch"
KEY_BYTES_MISSING = "notifications.frozenDocument.bytesMissing"
KEY_RANGE_INVALID = "notifications.frozenDocument.rangeInvalid"

#: The register's page ceiling. A regulator asks for a period, not for
#: everything; a seven-year utility holds ~532,000 documents (step 5f) and a
#: response that tried to carry them all would be the bulk export wearing a
#: request's clothes. The bulk export is its own background job and its own task.
REGISTER_MAX_ROWS = 500


# ═══════════════════════════════════════════════════════════════════════════
# SHAPING ONE DOCUMENT FOR A SCREEN
# ═══════════════════════════════════════════════════════════════════════════


def _split_rfc822(payload: bytes) -> tuple[str | None, str]:
    """An email artefact back into the subject and body that were SENT.

    ⚠ **THIS IS A PARSE, NOT A RENDER, and the difference is the whole rule.**
    `frozen_documents.artefact_bytes` froze a minimal RFC 5322 message — one
    `Subject:` header, a blank line, the body — precisely so the stored object is
    the thing a mail client and a human already read. Reading those two fields
    back out of the frozen bytes adds nothing and changes nothing; re-rendering
    them from `render_context` would produce today's wording, which is the defect.
    """
    message = message_from_bytes(payload, policy=email_policy)
    subject = message.get("Subject")
    body = message.get_payload(decode=False)
    return (str(subject) if subject is not None else None, body if isinstance(body, str) else "")


def _document_payload(reference: Any, *, verified: bytes) -> dict[str, Any]:
    """One frozen document as a screen receives it — never a storage key.

    `verified` is the payload `document_store.fetch()` has already hashed and
    approved. It is passed in rather than re-fetched so the bytes a caller reads
    and the bytes that were checked are provably the same object.
    """
    text: str | None = None
    subject: str | None = None
    if reference.content_type == "message/rfc822":
        subject, text = _split_rfc822(verified)
    else:
        # Print and SMS freeze the body as UTF-8 exactly as the vendor received
        # it (`artefact_bytes`). `errors="replace"` rather than a raise: a
        # document that cannot be decoded is still a document, and the person
        # asking to see it is better served by mojibake plus its hash than by a
        # 500 — the bytes have already been proved to be the frozen ones.
        text = verified.decode("utf-8", errors="replace")
    return {
        "id": str(reference.id),
        "kind": reference.kind,
        "channel": reference.channel,
        "display_name": reference.display_name,
        "content_type": reference.content_type,
        "content_hash": reference.content_hash,
        "byte_length": reference.byte_length,
        "stored_at": reference.stored_at.isoformat(),
        "storage_backend": reference.storage_backend,
        "subject": subject,
        "text": text,
        "download_url": document_store.download_url(reference.id),
        "url_expires_in_seconds": document_storage.url_ttl_seconds(),
    }


def _refuse_unreadable(problem: Exception, reference: Any) -> errors.BizError:
    """A stored document that will not read back is REPORTED, never softened.

    ⚠ **IT MUST NOT DEGRADE INTO "re-rendered from data".** That sentence is the
    honest answer when NO copy was kept. Here a copy WAS kept and its bytes are
    now wrong — a different fact, with a different remedy, and one somebody has
    to be told rather than have smoothed over by a reassuring caption. Hard-won
    law 1: a guarantee is worth nothing if its failure looks like a normal state.
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


def _read_or_refuse(reference: Any) -> dict[str, Any]:
    """Fetch (hash-verified), or raise the refusal that says which failure it is."""
    try:
        verified = document_store.fetch(reference.id)
    except (
        document_storage.ContentHashMismatch,
        document_storage.DocumentStorageError,
        document_store.DocumentStoreError,
    ) as problem:
        raise _refuse_unreadable(problem, reference) from problem
    return _document_payload(reference, verified=verified)


# ═══════════════════════════════════════════════════════════════════════════
# THE REPRINT — one sent message, reproduced
# ═══════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([AdminOrClerk])  # US-NOT-011 §5: the reprint sits beside the re-send, on S35
def outbound_document(request: Any, message_id: str) -> Response:
    """Show me what we actually sent this customer.

    Answers ONE of two states, and a screen must branch on `provenance`:

      * `original` — this IS the document the customer received, byte for byte,
        with `document` carrying it and its hash verified on this read.
      * `re_rendered_from_data_not_the_original` — no sealed copy exists, so
        **`document` is null** and `message_key` names the sentence that has to
        appear beside anything the screen shows instead.

    `exempt` separates the two innocent reasons for the second state — an in-app
    staff alert and a send test, both ruled out of the freeze by the PO — from
    the one that is a real gap. They are not the same fact and a screen should
    not say "we did not keep this" about a rehearsal.

    ⚠ A row still `queued` genuinely has no original. That is not a failure; it
    is the honest answer, and it is why this state cannot be deleted even once
    the dispatcher's precondition makes it unreachable for a `sent` row.
    """
    require_tenant(request)
    row = selectors.row_or_404(message_id)  # 404 == cross-tenant == unknown id
    reproduction = frozen_documents.reproduce(row)

    document = None
    if reproduction.is_original and reproduction.document is not None:
        document = _read_or_refuse(reproduction.document)

    return Response(
        {
            "message_id": str(row.pk),
            "channel": row.channel,
            "status": row.status,
            "template_code": row.template_code,
            # BR-NOT-025 / BR-BIL-026 — the pin is PROVENANCE ("which wording was
            # in force"), reported BESIDE the document rather than used to make
            # one. A reader who collapses the two will delete the wrong thing.
            "template_version": row.template_version,
            "provenance": reproduction.provenance,
            "is_original": reproduction.is_original,
            "exempt": reproduction.exempt,
            "unavailable_reason": reproduction.unavailable_reason,
            "message_key": reproduction.i18n_key,
            "detail": reproduction.detail,
            "document": document,
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# ONE FROZEN DOCUMENT, BY ITS OWN ID
# ═══════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def stored_document(request: Any, document_id: str) -> Response:
    """One document the register named, opened.

    The id came from a row this tenant could already see (`document_register`, or
    a reprint), and it is re-resolved under the caller's own tenant context here
    — a link is never issued for a document the caller could not have found.

    A document that does not exist and a document belonging to somebody else are
    **the same 404 with the same body** (HR-1). `document_store` raises the same
    `DocumentStoreError` for both and this converts it without inspecting it,
    because a handler that could tell them apart would eventually report the
    difference.
    """
    require_tenant(request)
    try:
        reference = document_store.reference(document_id)
    except (document_store.DocumentStoreError, ValueError, TypeError) as absent:
        raise errors.NotFoundError() from absent
    return Response(_read_or_refuse(reference))


# ═══════════════════════════════════════════════════════════════════════════
# THE REGULATOR REQUEST — a date range
# ═══════════════════════════════════════════════════════════════════════════


def _day(value: str | None, field: str) -> dt.date:
    """A calendar date from the query string, or a 422 that names the field.

    ⚠ **NEVER AN EMPTY LIST FOR A RANGE WE COULD NOT READ.** An empty register
    says *"this utility sent nothing that month"* — a statement about the utility
    — when the truth is that we did not understand the question. That is DEF-075's
    shape and it is worse here than anywhere: the reader is a regulator.
    """
    if not value:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key=KEY_RANGE_INVALID,
            field_errors=[{"field": field, "code": errors.VAL_REQUIRED}],
        )
    try:
        return dt.date.fromisoformat(value)
    except ValueError as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key=KEY_RANGE_INVALID,
            field_errors=[{"field": field, "code": errors.VAL_FORMAT}],
        ) from problem


@api_view(["GET"])
@permission_classes([SystemAdminOnly])  # CR-049 step 5f: the most sensitive read in the product
def document_register(request: Any) -> Response:
    """Every document this utility sealed between two dates — the regulator's list.

    `CR-048`'s E9 example is the case: *a regulator asking to see the exact
    disconnection letter a customer was sent last July*. This answers the first
    half — WHICH letters exist and what each one is — and `stored_document`
    opens one.

    **System Admin only** (step 5f: *"the MOST SENSITIVE OPERATION IN THE
    PRODUCT — every document a utility ever sent"*), and **audited**, because
    "who asked to see the whole file, and when" is exactly the question that
    follows a regulator request.

    ⚠ **A LIST, NOT A DOWNLOAD.** No bytes are read and no hash is verified here
    — verifying 500 documents to draw a table would fetch every object in the
    range. The verification happens when a document is OPENED, which is where a
    corrupted one has to be caught. The `content_hash` is reported so a caller
    holding an archive can check it against ours without asking us to.

    ⚠ **THE ENUMERATION IS A DATABASE QUERY** over `(tenant, stored_at)`. The bucket
    is never listed: it is slow at half a million objects and it is scoped by a
    string prefix, which one mistake turns into a cross-tenant read (step 5d
    decision 4). The table also returns what a listing never could — *the March
    bill for account ACC-1042* rather than a UUID.
    """
    require_tenant(request)
    query = request.query_params
    start = _day(query.get("from"), "from")
    end = _day(query.get("to"), "to")
    if end < start:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key=KEY_RANGE_INVALID,
            field_errors=[{"field": "to", "code": errors.VAL_RANGE}],
        )

    # Inclusive of both endpoints, which is what a person means by "July": the
    # upper bound is the instant the last day ENDS, not the instant it begins.
    since = dt.datetime.combine(start, dt.time.min, tzinfo=dt.timezone.utc)
    until = dt.datetime.combine(end, dt.time.max, tzinfo=dt.timezone.utc)

    rows = document_store.manifest(since=since, until=until, limit=REGISTER_MAX_ROWS + 1)
    truncated = len(rows) > REGISTER_MAX_ROWS
    rows = rows[:REGISTER_MAX_ROWS]

    core_audit.write_row(
        action="stored_document.register_read",
        entity_type="stored_document",
        entity_id=None,
        actor_user_id=getattr(getattr(request, "user", None), "id", None),
        after={"from": start.isoformat(), "to": end.isoformat(), "row_count": len(rows)},
    )

    return Response(
        {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "results": [
                {
                    "id": str(reference.id),
                    "kind": reference.kind,
                    "channel": reference.channel,
                    "display_name": reference.display_name,
                    "content_type": reference.content_type,
                    "content_hash": reference.content_hash,
                    "byte_length": reference.byte_length,
                    "stored_at": reference.stored_at.isoformat(),
                    "source_type": reference.source_type,
                    "source_id": str(reference.source_id),
                }
                for reference in rows
            ],
            # ⚠ STATED, never silently cut. A regulator reading 500 of 900 letters
            # and believing it is all of them is the failure this flag exists for.
            "truncated": truncated,
            "max_rows": REGISTER_MAX_ROWS,
        }
    )


urlpatterns = [
    # ⚠ ORDER MATTERS AND WAS CHECKED, NOT ASSUMED. `documents/register` is an
    # all-literal path and `documents/<str:document_id>` would otherwise swallow
    # it — Django resolves by URL and the FIRST match wins, so the literal is
    # declared first. `test_cr049_t3__the_reprint_routes_are_actually_mounted`
    # resolves both through the real root URLconf, so a future lane that reorders
    # them goes red here rather than serving a 404 for the register.
    path("documents/register", document_register),
    path("documents/<str:document_id>", stored_document),
    # `outbound/<id>/document` shares its first segment with `apps.notifications.
    # api`'s `outbound` family. It is safe: that module declares `outbound`,
    # `outbound/summary`, `outbound/requeue`, `outbound/<id>/requeue` and
    # `outbound/<id>/resend`, and Django matches whole segments — none of them is
    # `outbound/<id>/document`, and none is a prefix of it.
    path("outbound/<str:message_id>/document", outbound_document),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-049 task 3 (sources: 12-governance/11-change-requests.md CR-049 steps 5b/5c/5d(e)/5f and its 2026-08-30 amendments · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-027 · 06-backend/apps/tenancy/document_store.py, task 1's published service · 06-backend/apps/notifications/frozen_documents.py, task 2/7's reproduce())
# generated: 2026-08-30 by the CR-049 task 3 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — every route answered `404` over the real stack and `ImportError: cannot import name 'reprint_api'` before this module existed; the no-re-render assertion was shown failing against a draft that imported `rendering`. Verbatim transcripts in 06-backend/tests/test_cr049_t3_reprint_route.py and the lane report.
# exceptions: (1) A SINGLE-DOCUMENT READ FETCHES AS WELL AS LINKING, because a pre-signed URL is a direct client-to-cloud read that our hash check is not in the path of — argued in the module docstring. The BULK export keeps the opposite trade (step 5f) and is not built here. (2) NO BILL ROUTE. CR-049 task 4 has not stored a bill artefact, so a bill reprint would answer `document_not_stored` for every bill in the product; the honest state is served on the notification surface where documents actually exist, and `07-frontend/src/features/billing/BillDocumentPage.tsx` still re-renders — REPORTED as DEF-2530 rather than half-wired here. (3) THE REGISTER VERIFIES NO HASHES — a list of 500 would fetch 500 objects; verification is at open. (4) `document_store.reference()` and `manifest(until=…)` were ADDED to tenancy's published service rather than reached around; the table is tenancy's and B2 §2 forbids the alternative.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

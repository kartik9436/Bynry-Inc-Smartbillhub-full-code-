# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 P2.25 (lane MVI-WIZ-CUST, 2026-10-05) — a document the
#           clerk uploads on the move-in wizard's Customer step (image 39) waits
#           until Complete, then files on the new account.
# Rules:    BR-CUS-073 / BR-CUS-080 (a document is filed BY REFERENCE, never
#           copied) · BR-CUS-036 (the account's folders; carried papers are KYC)
#           · BR-CUS-095 (the move-in checklist, ships unticked) · BR-SHL-031
#           (PDF/PNG/JPG/CSV ≤ 10 MB — `account_documents.checked_file`) ·
#           BR-TEN-003 / HR-1 (another utility's card is "not staged", never
#           "forbidden") · hard-won law 14 (the filing is a savepoint)
# Tests:    06-backend/tests/test_cr171_p225_move_in_documents.py
# Called:   move_in_documents_api (the three doors) · move_in_people.pop /
#           write_at_complete (the `documents` key on the move-in commit)
# ───────────────────────────────────────────────────────
"""Stage a move-in document now; file it when the account exists.

**THE SAME CARRY AS THE REQUEST'S, ONE STEP EARLIER.** Lane MVI-IDN built
`move_in_people.carry_request_documents`: a request's stored file is filed on
the new account BY REFERENCE at Complete. A move-in started at the counter has
no request, so the file has nowhere to wait — the account it belongs on does
not exist until the clerk presses Complete (CR §9.IDN-2, *"Not here, stated"*).

**WHAT WAITS IS AN ACCOUNT DOCUMENT WHOSE FILING CARD IS NOT WRITTEN YET.**
:func:`stage` does exactly what `account_documents.file_document` does — the
same checks, the same store, the same kind and source type, the filing card's
id minted first and used as the stored document's `source_id` — and stops one
line short: the `account_documents` row. The card id rides in the wizard's
draft; at Complete :func:`file_staged` writes the card with THAT id on the new
account. So nothing new is stored, no table is added and no migration is
needed: the store already records "an account document, card X", and Complete
is the moment card X gets its account.

⚠ **A CARD IS PROVED BEFORE IT IS FILED, AND THE PROOF IS THE STORE'S OWN
ROW.** A `card_id` is accepted only when this tenant's store holds an
ACCOUNT-DOCUMENT whose `source_id` is that card and no filing card with that id
exists yet. A request's stored file, another utility's upload, a card already
filed or a made-up id all read the same: *not staged*. That is what stops this
key being a way to file somebody else's document on a new account.

⚠ **A DRAFT DISCARDED LEAVES ITS BYTES STORED.** The stored-document row is
write-once by trigger and BR-SHL-031 keeps a legal file seven years, so a file
staged on a draft nobody completes stays in the store, filed on nothing — the
same posture a request's removed upload already has. Recorded in the decision
log (2026-10-05, P2.25) rather than "cleaned up" by a delete nothing may run.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone


from apps.customers import models
from apps.customers import service_request_service as sr
from apps.customers.account_document_models import TYPE_KYC, AccountDocument
from apps.customers.account_documents import checked_file
from apps.tenancy import document_store
from apps.tenancy.document_models import (
    KIND_ACCOUNT_DOCUMENT,
    SOURCE_ACCOUNT_DOCUMENT,
    StoredDocument,
)
from core import audit as core_audit
from core import errors
from core.dbfields import uuid7
from core.tenancy import current_tenant_id

#: The folder a staged document is filed in — the request carry's own
#: (`move_in_people.CARRIED_DOC_FOLDER`): every paper a move-in brings is what
#: the utility was shown about who this customer is (BR-CUS-036).
FILED_FOLDER = TYPE_KYC

NOT_STAGED = "customers.moveIn.documents.notStaged"
TWICE = "customers.moveIn.documents.twice"
TYPE_UNKNOWN = "customers.serviceRequest.documentTypeUnknown"

_PROCESS = "customers.move_in_documents"


def _tenant_id() -> Any:
    tenant_id = current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _doc_type(value: Any) -> str | None:
    code = str(value or "").strip().lower()
    return code if code in models.ServiceRequestDocument.ATTACHABLE_DOC_TYPES else None


def required_types() -> list[str]:
    """The move-in checklist a clerk reads — the doc types the utility ticked
    for `move_in` on Settings, in designed order (`BR-CUS-095`).

    ⚠ **READ HERE BECAUSE THE SETTINGS DOOR IS SYSTEM ADMIN ONLY.** A billing
    clerk running a move-in cannot read `/service-request-settings/…`, and the
    Customer step's table (image 33) locks a row for each required type. An
    empty list is the shipped answer, never a gap.
    """
    return list(sr.required_document_types(models.ServiceRequest.OUTCOME_MOVE_IN))


def stage(actor: Any, payload: dict[str, Any], upload: Any) -> dict[str, Any]:
    """`POST /move-ins/documents` — store the bytes; mint the card; file nothing.

    Answers ``{card_id, doc_type, name, size_bytes, content_type}``. The
    ``doc_type`` is the CHECKLIST's word (*Tenancy or deed*), which is what
    the wizard's table shows; the folder it lands in at Complete is KYC.
    """
    tenant_id = _tenant_id()
    doc_type = _doc_type(payload.get("doc_type"))
    if doc_type is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key=TYPE_UNKNOWN,
            br_ref="BR-CUS-095",
            params={"value": str(payload.get("doc_type") or "")},
        )
    name, media_type, payload_bytes = checked_file(payload, upload)
    card_id = uuid7()
    moment = timezone.now()
    safe = name.replace("/", "-").replace("\\", "-").lstrip(".")
    # `account_documents._visible_name` reads the leaf back; with no account
    # number in front of it the leaf IS the name the clerk chose.
    display_name = f"account-documents/{moment:%Y}/{moment:%m}/{safe}"
    actor_id = getattr(actor, "id", None)
    ref = document_store.store(
        kind=KIND_ACCOUNT_DOCUMENT,
        source_type=SOURCE_ACCOUNT_DOCUMENT,
        source_id=card_id,
        content_type=media_type,
        display_name=display_name,
        payload=payload_bytes,
        actor_user_id=actor_id,
        process=None if actor_id else _PROCESS,
    )
    core_audit.write_row(
        action="customers.move_in.document_staged",
        entity_type="stored_document",
        entity_id=ref.id,
        actor_user_id=actor_id,
        after={
            "tenant_id": str(tenant_id),
            "card_id": str(card_id),
            "doc_type": doc_type,
            "byte_length": len(payload_bytes),
            "content_type": media_type,
        },
    )
    return {
        "card_id": str(card_id),
        "doc_type": doc_type,
        "name": safe,
        "size_bytes": len(payload_bytes),
        "content_type": media_type,
    }


def _staged(card_id: Any) -> StoredDocument | None:
    """This tenant's stored account document for `card_id`, still unfiled."""
    try:
        card = UUID(str(card_id))
    except (TypeError, ValueError):
        return None
    if AccountDocument.objects.filter(tenant_id=_tenant_id(), pk=card).exists():
        return None
    return (
        StoredDocument.objects.filter(
            tenant_id=_tenant_id(),
            kind=KIND_ACCOUNT_DOCUMENT,
            source_type=SOURCE_ACCOUNT_DOCUMENT,
            source_id=card,
        )
        .order_by("stored_at")
        .first()
    )


def content(actor: Any, card_id: Any, mode: str) -> dict[str, Any]:
    """`GET /move-ins/documents/{card}/content?as=view|download` — open a staged
    file before Complete.

    The account document's content route (`account_documents.document_content`)
    for a card that has no account yet: same modes, same inline list, same
    headers in the view, an audit row per open. A FILED card is the account's
    to open; here it is *not found*, as is another utility's (HR-1).
    """
    from apps.customers.account_documents import ALLOWED_CONTENT_TYPES
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
    stored = _staged(card_id)
    if stored is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    payload = document_store.fetch(stored.pk)
    content_type = (stored.content_type or "").split(";")[0].strip().lower()
    core_audit.write_row(
        action=(
            "customers.move_in.document_viewed"
            if mode == CONTENT_VIEW
            else "customers.move_in.document_downloaded"
        ),
        entity_type="stored_document",
        entity_id=stored.pk,
        actor_user_id=getattr(actor, "id", None),
        after={"card_id": str(card_id), "content_type": content_type, "bytes": len(payload)},
    )
    return {
        "payload": payload,
        "content_type": (
            content_type if content_type in ALLOWED_CONTENT_TYPES else "application/octet-stream"
        ),
        "name": stored.display_name.rsplit("/", 1)[-1] or "document",
        "inline": mode == CONTENT_VIEW and content_type in INLINE_CONTENT_TYPES,
    }


def pop_rows(raw: Any, fe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate the commit's `documents` list BEFORE any write.

    Each row is ``{card_id, doc_type}``. A row whose card is not staged — never
    staged, staged elsewhere, already filed — is refused by its index, and so
    is a card named twice: filing one stored file under two cards is the thing
    `uq_account_documents_document` refuses, and it is better said here.
    """
    if raw in (None, []):
        return []
    if not isinstance(raw, list):
        fe.append(_fe("documents", errors.VAL_FORMAT, "customers.account.unknown_field"))
        return []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(raw):
        at = f"documents[{index}]"
        if not isinstance(row, dict):
            fe.append(_fe(at, errors.VAL_FORMAT, "customers.account.unknown_field"))
            continue
        if _doc_type(row.get("doc_type")) is None:
            fe.append(_fe(f"{at}.doc_type", errors.VAL_UNKNOWN_LOOKUP, TYPE_UNKNOWN))
            continue
        card = str(row.get("card_id") or "").strip().lower()
        if card in seen:
            fe.append(_fe(at, errors.VAL_FORMAT, TWICE))
            continue
        stored = _staged(card)
        if stored is None:
            fe.append(_fe(at, errors.VAL_UNKNOWN_LOOKUP, NOT_STAGED))
            continue
        seen.add(card)
        rows.append(
            {"card_id": UUID(card), "document": stored, "doc_type": _doc_type(row.get("doc_type"))}
        )
    return rows


def evidence_cards(
    *, account: models.Account, rows: list[dict[str, Any]], service_request_id: Any = None
) -> list[str]:
    """`DEF-CUS-9780` — the filing cards on `account` that are *Assistance
    evidence*, so the discount claims of the same move-in can carry them as
    their proof. Call AFTER :func:`file_staged` and the request's carry.

    Two sources, the two ways evidence reaches a move-in: the wizard's own
    upload (the card id IS the account document id) and the request's papers
    (filed by reference, found by the stored document the request card points
    at). Every other checklist type — a deed, an ID — is not proof of
    assistance and is not offered as one.
    """
    evidence = models.ServiceRequestDocument.DOC_ASSISTANCE_EVIDENCE
    cards = [str(row["card_id"]) for row in rows if row.get("doc_type") == evidence]
    if service_request_id not in (None, ""):
        refs = []
        for ref in models.ServiceRequestDocument.objects.filter(
            tenant_id=account.tenant_id, request_id=service_request_id, doc_type=evidence
        ).values_list("storage_ref", flat=True):
            try:
                refs.append(UUID(str(ref)))
            except (TypeError, ValueError):
                continue
        if refs:
            cards += [
                str(one)
                for one in AccountDocument.objects.filter(
                    tenant_id=account.tenant_id, account_id=account.pk, document_id__in=refs
                )
                .order_by("uploaded_at", "id")
                .values_list("pk", flat=True)
            ]
    return list(dict.fromkeys(cards))


def file_staged(actor: Any, *, account: models.Account, rows: list[dict[str, Any]]) -> int:
    """Write each staged card on the account just opened. Inside the commit.

    The card keeps the id it was given at upload, points at the stored file it
    was given at upload, and carries whoever uploaded it and when — so the
    filing reads exactly as if it had been made on the account that day.
    """
    filed = 0
    for row in rows:
        stored = row["document"]
        with transaction.atomic():  # hard-won law 14
            filing = AccountDocument.objects.create(
                id=row["card_id"],
                tenant_id=account.tenant_id,
                account_id=account.pk,
                document_id=stored.pk,
                doc_type=FILED_FOLDER,
                uploaded_by_id=stored.stored_by_user_id,
                uploaded_by_process=None if stored.stored_by_user_id else _PROCESS,
                uploaded_at=stored.stored_at or timezone.now(),
            )
        core_audit.write_row(
            action="customers.account_document.filed_at_move_in",
            entity_type="account_document",
            entity_id=filing.pk,
            actor_user_id=getattr(actor, "id", None),
            after={
                "account_id": str(account.pk),
                "document_id": str(stored.pk),
                "doc_type": FILED_FOLDER,
            },
        )
        filed += 1
    return filed


def _fe(name: str, code: str, key: str) -> dict[str, Any]:
    return {"field": name, "code": code, "message_key": key, "params": {}}

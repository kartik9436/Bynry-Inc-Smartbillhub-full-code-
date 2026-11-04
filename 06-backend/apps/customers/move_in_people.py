# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 P1.10 · P1.11 (writes) · P1.26 (lane MVI-IDN, 2026-10-05) —
#           what a move-in brings with it besides the account: the people who
#           share it, the company's own facts, where the bill goes, and the
#           papers the applicant already handed over.
# Rules:    CR-171 §9.1 (the columns, `customers/0080`) · BR-CUS-092 (SSN and
#           licence encrypted, last four only on every read and audit row) ·
#           BR-CUS-1022 (a person and a company are never the same party) ·
#           BR-CUS-073 / BR-CUS-080 (documents carry over BY REFERENCE, never by
#           copy) · CR-031 statement 6 (*"move-in → all documents transfer to
#           it"*) · BR-CUS-036 (the account's five document folders) · hard
#           rule 2 (a percentage stored to six places, never a float) · hard
#           rule 8 (no address column on a person) · hard-won law 14 (a
#           savepoint around every write that may be refused)
# Tests:    06-backend/tests/test_cr171_p110_move_in_people.py
# Called:   services._move_in — `pop` before the transaction, `write_at_complete`
#           inside it, after the account and the move record exist.
# ───────────────────────────────────────────────────────
"""What a move-in brings with it, written in the same commit as the account.

**ONE MODULE, ONE CALL FROM `services._move_in`.** That function is written by
three lanes in this round (CR-171 §8.1: MONEY, FLOW and this one), so this lane
hands it two calls and nothing else: :func:`pop` before the transaction opens,
so a refused value writes nothing and the clerk keeps every field, and
:func:`write_at_complete` inside it, so a refused reading rolls these rows back
with the account they belong to (BR-SHL-019).

THE PAYLOAD KEYS (all optional; absent = nothing written)
---------------------------------------------------------
* ``co_owners`` — a list. On a PERSON's account each row is a CO-OWNER
  (image 38); on a COMPANY's an OWNER OR OFFICER (image 40). **The kind is the
  account holder's, never the clerk's**: a row that names the other kind is
  refused, because a co-owner of a company or an officer of a person is not a
  thing image 38 or 40 draws.
* ``company`` — ``{trading_as, business_type, registered_in}``, written onto the
  account holder's CUSTOMER row. Refused on a person (BR-CUS-1022).
* ``po_number`` · ``bills_go_to`` — two columns of the ACCOUNT (§9.1).
  ``bills_go_to = "contact_person"`` needs a contact on the account, and the
  move-in's existing ``contact`` block is that contact — whose ``job_title`` and
  ``contact_by`` are validated where every other contact field is
  (``services._validate_contact``), not here.

AND ONE THING WITH NO KEY: the move's request's documents (P1.26).

⚠ **A LINKED RETURNING COMPANY'S FACTS ARE OVERWRITTEN ONLY WHERE THE CLERK
TYPED A VALUE.** A blank in the form is *not asked*, never *erase what we
hold*; the before and after go to `audit_log`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.customers import co_owner_models, models
from apps.customers.account_document_models import TYPE_KYC, AccountDocument
from core import audit as core_audit
from core import crypto, errors

#: The keys :func:`pop` takes off a move-in payload. `services.MOVE_IN_FIELDS`
#: admits them; nothing else reads them.
PAYLOAD_KEYS: tuple[str, ...] = (
    "co_owners",
    "company",
    "po_number",
    "bills_go_to",
    # CR-171-BRC10 P2.25 (lane MVI-WIZ-CUST) — papers the clerk uploaded on the
    # wizard itself (image 39), staged by `move_in_documents.stage` and filed
    # here at Complete beside the request's (`carry_request_documents`).
    "documents",
)

#: What a co-owner card (image 38) and an officer card (image 40) may carry.
CO_OWNER_FIELDS: frozenset[str] = frozenset(
    {
        "full_name",
        "relationship",
        "title",
        "ownership_pct",
        "signs_for_company",
        "personal_guarantee",
        "date_of_birth",
        "ssn",
        "driving_licence",
        "phone",
        "email",
        "contact_by",
        "responsible_for_bills",
    }
)
#: The four facts only an OFFICER has; the database refuses them on a co-owner
#: too (`ck_account_co_owners_*`), and this refuses them first, by field name.
OFFICER_ONLY: frozenset[str] = frozenset(
    {"title", "ownership_pct", "signs_for_company", "personal_guarantee"}
)
#: …and the one only a CO-OWNER has.
CO_OWNER_ONLY: frozenset[str] = frozenset({"relationship"})

COMPANY_FIELDS: tuple[str, ...] = ("trading_as", "business_type", "registered_in")

#: Every document a request carries lands in the account's KYC folder
#: (BR-CUS-036): proof of identity, of address, a deed, an authority to act — all
#: are what the utility was shown about who this customer is. `contract` is
#: audit-locked and means *countersigned by us*, which a document the APPLICANT
#: brought is not; `system` is the product's own.
CARRIED_DOC_FOLDER = TYPE_KYC

_MAX = 200


@dataclass
class Block:
    """The validated values, held between :func:`pop` and the write."""

    co_owners: list[dict[str, Any]] = field(default_factory=list)
    company: dict[str, str] = field(default_factory=dict)
    account: dict[str, str | None] = field(default_factory=dict)
    #: P2.25 — `[{card_id, document}]`, each card proved staged by `pop`.
    documents: list[dict[str, Any]] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.co_owners or self.company or self.account or self.documents)


def _fe(name: str, code: str, key: str, **params: Any) -> dict[str, Any]:
    return {"field": name, "code": code, "message_key": key, "params": params}


def _refuse(fe: list[dict[str, Any]]) -> None:
    if fe:
        raise errors.ValidationError(
            fe[0]["code"], message_key=fe[0]["message_key"], params=fe[0]["params"], field_errors=fe
        )


def _refuse_state(name: str, key: str, br_ref: str) -> None:
    """A refusal about the ACCOUNT's state rather than a typed value (409).

    Raised inside `_move_in`'s transaction, so the account and the move record
    roll back with it; `field_errors` still names the input to fix."""
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref=br_ref,
        message_key=key,
        params={},
        field_errors=[_fe(name, errors.BIZ_STATE, key)],
    )


def _text(value: Any, limit: int = _MAX) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned[:limit] if cleaned else None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def pop(data: dict[str, Any]) -> Block:
    """Take this module's keys off ``data`` and validate them — before any write.

    ``data`` is the move-in's own copy (``services._move_in`` copies the
    payload before popping), so popping is the same act ``initial_reads`` and
    ``deposit`` already take: the account write never sees a key that is not an
    account column, and a refusal here leaves the clerk every other field.
    """
    raw = {key: data.pop(key) for key in PAYLOAD_KEYS if key in data}
    block = Block()
    fe: list[dict[str, Any]] = []

    rows = raw.get("co_owners")
    if rows not in (None, []):
        if not isinstance(rows, list):
            fe.append(_fe("co_owners", errors.VAL_FORMAT, "customers.account.unknown_field"))
        else:
            for index, row in enumerate(rows):
                cleaned = _clean_person(row, f"co_owners[{index}]", fe)
                if cleaned is not None:
                    block.co_owners.append(cleaned)

    company = raw.get("company")
    if company not in (None, {}):
        if not isinstance(company, dict):
            fe.append(_fe("company", errors.VAL_FORMAT, "customers.account.unknown_field"))
        else:
            for name in sorted(set(company) - set(COMPANY_FIELDS)):
                fe.append(
                    _fe(f"company.{name}", errors.VAL_FORMAT, "customers.account.unknown_field")
                )
            for name in COMPANY_FIELDS:
                value = _text(company.get(name))
                if value is not None:
                    block.company[name] = value

    if "po_number" in raw:
        block.account["po_number"] = _text(raw.get("po_number"), 60)
    if "bills_go_to" in raw:
        value = _text(raw.get("bills_go_to"))
        if value is not None and value not in models.BILLS_GO_TO:
            fe.append(
                _fe(
                    "bills_go_to",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "customers.moveIn.people.choiceUnknown",
                )
            )
        block.account["bills_go_to"] = value

    if "documents" in raw:
        # P2.25 — proved BEFORE the transaction: a card that is not staged here
        # refuses the move-in by its index and nothing is written.
        from apps.customers import move_in_documents

        block.documents = move_in_documents.pop_rows(raw.get("documents"), fe)

    _refuse(fe)
    return block


def _clean_person(row: Any, at: str, fe: list[dict[str, Any]]) -> dict[str, Any] | None:
    """One card. Kind-specific fields are checked at write time, against the
    holder's kind — the only moment the kind is known."""
    if not isinstance(row, dict):
        fe.append(_fe(at, errors.VAL_FORMAT, "customers.account.unknown_field"))
        return None
    for name in sorted(set(row) - CO_OWNER_FIELDS):
        fe.append(_fe(f"{at}.{name}", errors.VAL_FORMAT, "customers.account.unknown_field"))
    out: dict[str, Any] = {}
    out["full_name"] = _text(row.get("full_name"))
    if not out["full_name"]:
        fe.append(_fe(f"{at}.full_name", errors.VAL_REQUIRED, "customers.contact.name_required"))
    for name in ("relationship", "title", "phone"):
        out[name] = _text(row.get(name), 80 if name == "phone" else _MAX)
    email = _text(row.get("email"), 254)
    if email and ("@" not in email or email.startswith("@") or email.endswith("@")):
        fe.append(_fe(f"{at}.email", errors.VAL_FORMAT, "customers.contact.email_format"))
    out["email"] = email
    contact_by = _text(row.get("contact_by"))
    if contact_by is not None and contact_by not in models.CONTACT_BY:
        fe.append(
            _fe(
                f"{at}.contact_by",
                errors.VAL_UNKNOWN_LOOKUP,
                "customers.moveIn.people.choiceUnknown",
            )
        )
    out["contact_by"] = contact_by
    dob = row.get("date_of_birth")
    out["date_of_birth"] = None
    if dob not in (None, ""):
        from datetime import date

        try:
            out["date_of_birth"] = date.fromisoformat(str(dob)[:10])
        except ValueError:
            fe.append(
                _fe(f"{at}.date_of_birth", errors.VAL_FORMAT, "customers.account.date_invalid")
            )
    pct = row.get("ownership_pct")
    out["ownership_pct"] = None
    if pct not in (None, ""):
        # Hard rule 2 — `Decimal(str(value))`, never a float; percentage points.
        try:
            value = Decimal(str(pct))
        except (InvalidOperation, ValueError):
            value = None
        if value is None or not value.is_finite() or value < 0 or value > 100:
            fe.append(
                _fe(
                    f"{at}.ownership_pct",
                    errors.VAL_RANGE,
                    "customers.moveIn.people.shareRange",
                )
            )
        else:
            out["ownership_pct"] = value
    for name in ("signs_for_company", "personal_guarantee", "responsible_for_bills"):
        out[name] = _bool(row.get(name)) if name in row else False
    for name in ("ssn", "driving_licence"):
        out[name] = _text(row.get(name), 64)
    # Remember which kind-specific fields were actually SENT, so the kind check
    # at write time refuses a sent field and never a default.
    out["_sent"] = frozenset(name for name in row if row.get(name) not in (None, "", False))
    return out


# ═══════════════════════════════════════════════════════════════════════════
# THE WRITE — inside `_move_in`'s transaction
# ═══════════════════════════════════════════════════════════════════════════
def write_at_complete(
    actor: Any, *, account_id: Any, block: Block, service_request_id: Any = None
) -> dict[str, Any]:
    """Write the block onto the account just opened; carry the request's papers.

    Answers what was written, for the *Move-in completed* screen's *What
    happened* (P1.21): ``{"co_owners": n, "company_updated": [...],
    "documents_carried": n}``. Identifiers never appear in the answer.
    """
    account = models.Account.objects.get(pk=account_id)
    holder = _holder(account)
    fe: list[dict[str, Any]] = []
    actor_id = getattr(actor, "id", None)

    # ── the account's two columns ────────────────────────────────────────
    if block.account:
        if block.account.get("bills_go_to") == "contact_person" and not _has_contact(account):
            _refuse_state("bills_go_to", "customers.moveIn.people.contactNeeded", "BR-BIL-036")
        before = {name: getattr(account, name) for name in block.account}
        for name, value in block.account.items():
            setattr(account, name, value)
        account.save(update_fields=list(block.account))
        core_audit.write_row(
            action="customers.account.billing_route_set",
            entity_type="account",
            entity_id=account.pk,
            actor_user_id=actor_id,
            before=before,
            after=dict(block.account),
        )

    # ── the company's own facts, on the holder's customer row ───────────
    company_updated: list[str] = []
    if block.company:
        if holder is None or holder.kind != "company":
            _refuse_state("company", "customers.moveIn.people.companyOnly", "BR-CUS-1022")
        before = {name: getattr(holder, name) for name in block.company}
        changed = {name: v for name, v in block.company.items() if before[name] != v}
        if changed:
            for name, value in changed.items():
                setattr(holder, name, value)
            holder.save(update_fields=[*changed, "updated_at"])
            core_audit.write_row(
                action="customers.customer.company_facts_set",
                entity_type="customer",
                entity_id=holder.pk,
                actor_user_id=actor_id,
                before={name: before[name] for name in changed},
                after=changed,
            )
            company_updated = sorted(changed)

    # ── co-owners / owners and officers ──────────────────────────────────
    kind = (
        co_owner_models.KIND_OFFICER
        if holder is not None and holder.kind == "company"
        else co_owner_models.KIND_CO_OWNER
    )
    wrong = OFFICER_ONLY if kind == co_owner_models.KIND_CO_OWNER else CO_OWNER_ONLY
    for index, person in enumerate(block.co_owners):
        for name in sorted(person["_sent"] & wrong):
            fe.append(
                _fe(
                    f"co_owners[{index}].{name}",
                    errors.VAL_FORMAT,
                    "customers.moveIn.people.officerOnly"
                    if kind == co_owner_models.KIND_CO_OWNER
                    else "customers.moveIn.people.coOwnerOnly",
                )
            )
    _refuse(fe)
    written = 0
    for person in block.co_owners:
        row = co_owner_models.AccountCoOwner(
            tenant_id=account.tenant_id,
            account=account,
            kind=kind,
            full_name=person["full_name"],
            relationship=person["relationship"] if kind == co_owner_models.KIND_CO_OWNER else None,
            title=person["title"] if kind == co_owner_models.KIND_OFFICER else None,
            ownership_pct=person["ownership_pct"] if kind == co_owner_models.KIND_OFFICER else None,
            signs_for_company=kind == co_owner_models.KIND_OFFICER and person["signs_for_company"],
            personal_guarantee=kind == co_owner_models.KIND_OFFICER
            and person["personal_guarantee"],
            date_of_birth=person["date_of_birth"],
            phone=person["phone"],
            email=person["email"],
            contact_by=person["contact_by"],
            responsible_for_bills=person["responsible_for_bills"],
        )
        for name in ("ssn", "driving_licence"):
            co_owner_models.set_identifier(row, name, person[name])
        # Hard-won law 14 — a refused row must not poison the move-in's
        # transaction on PostgreSQL; the savepoint is what makes the refusal
        # land as a refusal and not as `InFailedSqlTransaction` two lines on.
        with transaction.atomic():
            row.save()
        core_audit.write_row(
            action="customers.account.co_owner_added",
            entity_type="account_co_owner",
            entity_id=row.pk,
            actor_user_id=actor_id,
            # BR-CUS-092 — last four only in an audit `details` blob.
            after={
                "account_id": str(account.pk),
                "kind": kind,
                "full_name": row.full_name,
                "ssn_last4": crypto.last_four(row.ssn) if row.ssn else None,
                "driving_licence_last4": (
                    crypto.last_four(row.driving_licence) if row.driving_licence else None
                ),
                "responsible_for_bills": row.responsible_for_bills,
            },
        )
        written += 1

    carried = carry_request_documents(actor, account=account, service_request_id=service_request_id)
    if block.documents:
        # P2.25 — the wizard's own uploads, counted with the request's: *What
        # happened* says how many papers reached the account, not where from.
        from apps.customers import move_in_documents

        carried += move_in_documents.file_staged(actor, account=account, rows=block.documents)
    return {
        "co_owners": written,
        "company_updated": company_updated,
        "documents_carried": carried,
    }


def _holder(account: models.Account) -> models.Customer | None:
    """The customer `_open_account` linked this account to — the first link."""
    link = (
        models.CustomerAccount.objects.filter(tenant_id=account.tenant_id, account_id=account.pk)
        .select_related("customer")
        .order_by("created_at", "id")
        .first()
    )
    return link.customer if link is not None else None


def _has_contact(account: models.Account) -> bool:
    return models.Contact.objects.filter(
        tenant_id=account.tenant_id, account=account, deleted_at__isnull=True
    ).exists()


# ═══════════════════════════════════════════════════════════════════════════
# P1.26 — THE REQUEST'S DOCUMENTS REACH THE ACCOUNT, BY REFERENCE
# ═══════════════════════════════════════════════════════════════════════════
def carry_request_documents(actor: Any, *, account: models.Account, service_request_id: Any) -> int:
    """File every document the move's request holds onto the new account.

    ⚠ **BY REFERENCE, NEVER BY COPY (BR-CUS-080, BR-CUS-073).** The account's
    filing card points at the SAME stored document the request's card points at
    (`service_request_documents.storage_ref` is that row's id), so one uploaded
    file stays ONE stored object, nothing is re-uploaded, and the request keeps
    its own card. The uploader and the moment it was handed over travel with the
    card, so the audit trail of who supplied it survives the hand-off.

    **ALL OF THEM, NOT ONLY THE CHECKLIST'S** — CR-031 statement 6: *"move-in →
    all documents transfer to it."* A tenant whose checklist ticks nothing still
    has the applicant's papers on the account.

    **Skipped, and counted out:** a card with no stored file (a tick nobody
    attached), a `storage_ref` that is not a stored document of this tenant
    (the sample data's `sample-data://` references), and a file already filed on
    some account (`uq_account_documents_document` — one filing per stored
    file).
    """
    if service_request_id in (None, ""):
        return 0
    from apps.tenancy.document_models import StoredDocument

    cards = list(
        models.ServiceRequestDocument.objects.filter(
            tenant_id=account.tenant_id, request_id=service_request_id
        )
        .exclude(storage_ref__isnull=True)
        .exclude(storage_ref="")
        .order_by("created_at", "id")
    )
    refs = {}
    for card in cards:
        try:
            refs[card.pk] = UUID(str(card.storage_ref))
        except ValueError:
            continue
    stored = set(
        StoredDocument.objects.filter(
            tenant_id=account.tenant_id, pk__in=list(refs.values())
        ).values_list("pk", flat=True)
    )
    already = set(
        AccountDocument.objects.filter(
            tenant_id=account.tenant_id, document_id__in=list(stored)
        ).values_list("document_id", flat=True)
    )
    carried = 0
    for card in cards:
        ref = refs.get(card.pk)
        if ref is None or ref not in stored or ref in already:
            continue
        with transaction.atomic():  # hard-won law 14
            filing = AccountDocument.objects.create(
                tenant_id=account.tenant_id,
                account_id=account.pk,
                document_id=ref,
                doc_type=CARRIED_DOC_FOLDER,
                uploaded_by_id=card.uploaded_by_id,
                uploaded_by_process=None if card.uploaded_by_id else "customers.move_in",
                uploaded_at=card.uploaded_at or timezone.now(),
            )
        already.add(ref)
        core_audit.write_row(
            action="customers.account_document.carried",
            entity_type="account_document",
            entity_id=filing.pk,
            actor_user_id=getattr(actor, "id", None),
            after={
                "account_id": str(account.pk),
                "document_id": str(ref),
                "from_request_document_id": str(card.pk),
                "request_doc_type": card.doc_type,
                "doc_type": CARRIED_DOC_FOLDER,
            },
        )
        carried += 1
    return carried


# ═══════════════════════════════════════════════════════════════════════════
# P2.24 — A CO-OWNER'S PHOTO ID, ONCE THE ACCOUNT EXISTS (lane MVI-WIZ-CUST)
# ═══════════════════════════════════════════════════════════════════════════
def attach_photo_id(
    actor: Any, account_id: Any, co_owner_id: Any, payload: dict[str, Any], upload: Any
) -> dict[str, Any]:
    """`POST /accounts/{id}/co-owners/{coOwnerId}/photo-id` — file the photo ID.

    Image 38 draws *Photo ID [Upload]* on the wizard's card, but the photo is a
    filing card ON THE ACCOUNT (`photo_id_document_id` → `account_documents`),
    and the account does not exist until Complete (§9.IDN-2, *"Not here,
    stated"*). So the upload happens here, after: the file is filed exactly as
    `POST /accounts/{id}/documents` files it (`account_documents.file_document`
    — same checks, same store, KYC folder) and the co-owner row then points at
    that filing. A second upload points the row at the newer filing; the older
    one stays filed (a filing is withdrawn, never deleted — `BR-CUS-1052`).

    A co-owner who is not on THIS account — another account's, another
    utility's — is the same 404 as one that never existed (HR-1).
    """
    from apps.customers import account_documents

    account = account_documents._account_or_404(account_id)
    row = co_owner_models.AccountCoOwner.objects.filter(
        tenant_id=account.tenant_id, account_id=account.pk, pk=co_owner_id
    ).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    filed = account_documents.file_document(
        actor, account.pk, {**payload, "doc_type": TYPE_KYC}, upload
    )
    before = str(row.photo_id_document_id) if row.photo_id_document_id else None
    with transaction.atomic():  # hard-won law 14
        row.photo_id_document_id = filed["id"]
        row.save(update_fields=["photo_id_document", "updated_at"])
    core_audit.write_row(
        action="customers.account.co_owner_photo_id_filed",
        entity_type="account_co_owner",
        entity_id=row.pk,
        actor_user_id=getattr(actor, "id", None),
        before={"photo_id_document_id": before},
        after={"photo_id_document_id": filed["id"], "account_id": str(account.pk)},
    )
    return {"co_owner_id": str(row.pk), "photo_id": True, "document_id": filed["id"]}

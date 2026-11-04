# ── Trace ──────────────────────────────────────────────
# Change:   BR-CUS-1054 — **a customer's own details can be corrected.** PO
#           2026-09-13, verbatim: *"Start the customer edit one also - we will
#           need this"*. Until this file, `GET /customers/{id}` was read-only
#           and NO door in the product could fix a misspelt name, a wrong
#           telephone number or a wrong email. `CR-094-BRC01` wave R.
# Rules:    BR-CUS-1054 (the instruction) · BR-CUS-054 (one customer, many
#           accounts — an email correction therefore reaches them all) ·
#           BR-CUS-092(c) (last four only; the full identifier never reaches a
#           list response, an export, a log line or an audit blob) ·
#           BR-CUS-1020 (identity lives on the customer, encrypted, each
#           identifier with a blind index beside it) · BR-CUS-1022 (identity is
#           per KIND — neither kind borrows the other's evidence) ·
#           BR-CWP-026 (a refused field is refused BY NAME, never dropped) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 4 (issued bills
#           do not restate) · hard rule 7 (every change audited before→after) ·
#           hard rule 8 (an address lives on the premises; `kind='mailing'` is
#           its named exception and is NOT written here) · hard-won law 14 (a
#           unique clash is caught inside a SAVEPOINT or PostgreSQL loses the
#           whole transaction while SQLite passes every test).
# Tests:    06-backend/tests/test_br_cus_1054_customer_edit.py
# Impacts:  apps/customers/api.py (the PATCH route) ·
#           07-frontend/src/features/customers/CustomerEditDialog.tsx
# ───────────────────────────────────────────────────────
"""The clerk's door onto a customer's own record.

⚠ **WHY THIS IS NOT A SECOND COPY OF `update_account`.** The two touch
different tables and only one of them is PII. `update_account` writes columns
on `accounts`; not one of the fields a clerk means by *"the customer's details"*
is on that table, so `update_account` neither accepted nor refused them — it
had never heard of them.

⚠ **THE FAILURE THIS FILE EXISTS TO NOT SHIP IS A STALE BLIND INDEX.** Four
columns here are app-layer encrypted under a randomised scheme, and each has a
deterministic `*_bidx` token beside it that is the ONLY way the row can be
found by that value. Write a corrected phone straight onto the column and the
stored value is right while the index still points at the old number: the
customer becomes unfindable by the very number that was just corrected, and
**every test that reads the field back passes**, because the field IS correct.
So nothing here ever assigns an identifier directly. `identity_match.
set_identifier` is the one writer, it sets the ciphertext and the token in one
act, and it has always said so in its own docstring. The proof that matters is
in `test_br_cus_1054_customer_edit.py`: it corrects a phone and then SEARCHES
for the new one through `selectors.customer_list`, which is the path a clerk
uses. A read-back test would have passed on the broken version.

⚠ **THE PORTAL SIGN-IN IS A DIFFERENT COLUMN AND MOVES ONLY WHEN THE CLERK
TICKS FOR IT.** `apps/portal` holds its own `email`, which is the sign-in
identifier, unique per tenant and normalised through
`credentials.normalise_email`. It is another module's table (B2 §2 forbids the
write), and moving it quietly would either lock a customer out of the portal or
hand their account to a new address. **`OQ-CUS-12350` is CLOSED (PO
2026-10-22):** *"give option to clark to make it log in email also if they
choose it make login and bill email sent otherwise keep them separate"*. So
`portal_sign_in: true` (the tick box, unticked by default) asks the PORTAL's own
function to move it (`portal_seam.move_portal_sign_in`); without the tick the
two stay separate, exactly as before.

⚠ **ISSUED BILLS DO NOT RESTATE.** A bill's customer name is locked into its
snapshot at issue (hard rule 4), so a correction changes the NEXT bill and
nothing already sent. That is a sentence the screen carries, not a caveat
buried here.

⚠ **THE MAILING ADDRESS IS NOT WRITTEN HERE, AND IT IS REFUSED BY NAME.**
`customers.addresses` `kind='mailing'` is hard rule 8's named exception and it
hangs off the ACCOUNT, six parts, with `BR-CWP-086`'s returned-post clearing
riding on it. `portal_self_service._write_address` is the one writer and a
second one is a second address home in all but name. ⚠ **Measured 2026-09-13:
NO CLERK DOOR UPDATES AN ADDRESS OR A CONTACT ANYWHERE IN THIS PRODUCT** —
`contacts` and `addresses` are created at account-create and thereafter written
only from the customer PORTAL. That is a real gap, it is recorded in the
decision log of 2026-09-13, and it is its own wave rather than something this
one closes on the way past. This file is the first clerk door onto a contact at
all, and it moves the EMAIL only.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models.functions import Lower

from apps.customers import identity_match, models, seams
from core import audit as core_audit
from core import crypto
from core import errors
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

#: The plain columns on `customers` this door may set.
PLAIN_FIELDS: tuple[str, ...] = ("display_name", "external_ref", "date_of_birth")

#: The encrypted identifiers, every one of which goes through
#: `identity_match.set_identifier` so its blind index moves with it.
IDENTIFIER_FIELDS: tuple[str, ...] = ("ssn", "driving_licence", "phone", "tax_id")

#: `email` has NO column on `customers` at all — it lives on `contacts`, which
#: hangs off the account. It is accepted here because a clerk correcting *the
#: customer's details* means it, and `BR-CUS-054`'s N:M link is what says where
#: it goes: EVERY account this person holds.
CONTACT_FIELDS: tuple[str, ...] = ("email", "contact_by")
#: ⊕ `DEF-CUS-10253` — *Contact by* (image `08-edit.png`, PO 2026-10-18: the
#: edit dialogs use the shared customer fields). Like `email` it has no column
#: on `customers`: it is `contacts.contact_by`, written on EVERY account this
#: person holds, from the one list (`models.CONTACT_BY`).

#: CR-161-BRC10 W4 — the utility's OWN fields on a customer (PO 2026-10-02,
#: Part 2 row 2: *"Customer edit"*). Validated and MERGED by tenancy's one
#: validator through `seams.validate_custom_data` with `screen=CUSTOM_SCREEN`.
CUSTOM_FIELDS_KEY = "custom_data"
CUSTOM_SCREEN = "CUSTOMER_EDIT"

#: ⊕ PO 2026-10-22 (closes `OQ-CUS-12350`, `DEF-CWP-10400`), verbatim: *"give
#: option to clark to make it log in email also if they choose it make login
#: and bill email sent otherwise keep them separate"*. Not a field: a tick box,
#: unticked by default. `true` moves the portal sign-in to the email saved in
#: the same request; absent or anything else moves nothing, exactly as before.
SIGN_IN_FLAG = "portal_sign_in"

EDITABLE_FIELDS: frozenset[str] = frozenset(
    PLAIN_FIELDS + IDENTIFIER_FIELDS + CONTACT_FIELDS + (CUSTOM_FIELDS_KEY, SIGN_IN_FLAG)
)

#: What the portal's `staff_move_sign_in` may refuse, as the clerk's field
#: error: (field, message key). Shared by both clerk doors.
SIGN_IN_REFUSALS: dict[str, tuple[str, str]] = {
    "no_login": (SIGN_IN_FLAG, "customers.customer.edit.signInNoLogin"),
    "email_required": ("email", "customers.customer.edit.signInNeedsEmail"),
    "email_invalid": ("email", "customers.customer.edit.signInEmailInvalid"),
    "taken": ("email", "customers.customer.edit.signInTaken"),
}


def move_sign_in(actor: Any, tenant_id: Any, customer_id: Any, email: Any) -> bool:
    """The clerk's tick: move the customer's portal login to `email`.

    Through `portal_seam.move_portal_sign_in` — the portal writes its own row
    (B2 §2). Runs inside the caller's transaction, so a refusal raised here
    rolls the contact write back with it. Returns whether the login moved (an
    address that already IS the sign-in email moves nothing and sends nothing).
    """
    from apps.customers import portal_seam

    answer = portal_seam.move_portal_sign_in(
        tenant_id,
        customer_id=customer_id,
        email=email,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
    )
    result = answer.get("result")
    if result in SIGN_IN_REFUSALS:
        field, key = SIGN_IN_REFUSALS[result]
        _refuse([_field_error(field, errors.VAL_FORMAT, key)])
    return result == "moved"

#: ⚠ **REFUSED BY NAME, NEVER IGNORED** (`BR-CWP-026`'s posture, and
#: `DEF-632`'s lesson: a silently dropped field is a screen that says *saved*
#: over a value that went nowhere). Each entry names the rule that owns the
#: field and says who is entitled to write it — answering *"unknown field"*
#: here would hide a real answer, because the field EXISTS.
REFUSED_FIELDS: dict[str, tuple[str, str]] = {
    "customer_no": (
        "BR-CUS-1023",
        "OUR number for this customer, allocated from the tenant's `customer` series inside "
        "the transaction that creates the row — there is no input path and re-keying one "
        "would break every letter that already quotes it",
    ),
    # ⚠ **THE KIND IS REFUSED AND THIS IS THE ONE REFUSAL WORTH READING TWICE.**
    # `BR-CUS-1022`: a person is known by SSN, licence or phone; a company by
    # its Tax ID, and *neither kind borrows the other's criteria*. Flipping the
    # kind on a row that already carries identity would leave every identifier
    # STORED, INVISIBLE AND PERMANENTLY UNMATCHABLE — the matcher for the new
    # kind never reads those columns — which `identity_match.set_identifier`
    # already refuses to do one field at a time. Doing it wholesale from an
    # edit form would walk around that refusal. Correcting a person filed as a
    # company is a real need and it is a different act with its own rules:
    # `OQ-CUS-12351`.
    "kind": (
        "BR-CUS-1022",
        "a person is identified by SSN, licence or phone and a company by its Tax ID; "
        "changing the kind would strand every identifier already on file in a column the "
        "matcher for the new kind never reads",
    ),
    "postal": (
        "BR-CUS-1054",
        "the mailing address hangs off the ACCOUNT and clearing returned post rides on it "
        "(BR-CWP-086) — this door writes the customer's own record and no second address "
        "writer is opened here",
    ),
    "address": ("BR-MET-1161", "an address lives on the premises; the mailing address is the "
                "account's named exception and is not written from here"),
    "accounts": ("BR-CUS-054", "the customer↔account link carries a confirmed match tier and is "
                 "made at the counter, never on an edit form"),
    "match_tier": ("BR-CUS-089", "the tier is stored with its CONFIRMER at the moment a human "
                   "commits the match"),
    "match_basis": ("BR-CUS-089", "recorded with the tier, by the person who made the match"),
    "is_sample": ("BR-TEN-057", "written only by this module's own sample-data path"),
    "ssn_bidx": ("BR-CUS-1020", "the blind index is DERIVED from the identifier and is written "
                 "with it, never separately"),
    "driving_licence_bidx": ("BR-CUS-1020", "derived from the identifier, never set directly"),
    "phone_bidx": ("BR-CUS-1020", "derived from the identifier, never set directly"),
    "tax_id_bidx": ("BR-CUS-1020", "derived from the identifier, never set directly"),
    "portal_email": (
        "BR-CWP-004",
        "the portal sign-in is another module's table and is never set directly — it follows "
        "the contact email only when portal_sign_in is ticked (PO 2026-10-22)",
    ),
    "tenant": ("BR-TEN-003", "the tenant is the request's, never a payload's"),
    "id": ("BR-SHL-014", "the row's key is not a field"),
}

#: What `_audit` masks before a value reaches `audit_log`. `BR-CUS-092(c)`
#: verbatim: *"the full value is never in a list response, an export, a log line
#: or an audit `details` blob"*.
#:
#: ⚠ **THE MASKING IS AT THE BOUNDARY AND NOT AT THE CALL SITES**, which is the
#: shape `service_request_service._audit` already took and the reason it gives
#: is the right one: an `EncryptedTextField` hands back the DECRYPTED value on
#: attribute access, so every `before` blob in this file is cleartext until it
#: passes through here. Masking per call site works until the next writer in
#: this module forgets, and a forgotten one is invisible — the row writes,
#: nothing raises, and the number sits in `audit_log` forever.
#:
#: ⚠ **`phone` IS DELIBERATELY NOT MASKED, AND THAT IS A JUDGMENT WITH A
#: REASON.** `BR-CUS-092` names two government identifiers and a telephone
#: number is neither; `selectors.customer_row` already serves the phone in full
#: to the browser and `customer_list` searches on it. Masking it HERE alone
#: would leave the one record that exists to answer *"what was the old number"*
#: unable to answer it, on the single most common correction this door will
#: ever take. Recorded in the decision log of 2026-09-13 rather than left to be
#: inferred from this absence.
AUDIT_MASKED_FIELDS: frozenset[str] = frozenset({"ssn", "driving_licence", "tax_id"})

#: How far a text column may run. `display_name` and `external_ref` are TEXT in
#: PostgreSQL, so this is a form limit rather than a column one.
_MAX_TEXT = 200


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:_MAX_TEXT] if text else None


def _field_error(field: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": code, "message_key": message_key, "params": params}


def _refuse(field_errors: list[dict[str, Any]]) -> None:
    if field_errors:
        raise errors.ValidationError(
            field_errors[0]["code"],
            message_key=field_errors[0]["message_key"],
            params=field_errors[0]["params"],
            field_errors=field_errors,
        )


def reject_unknown(payload: dict[str, Any]) -> None:
    """Every key is editable, refused-with-its-rule, or unknown.

    ⚠ **THE ORDER MATTERS AND IT IS THE ONE THING TO GET RIGHT HERE.** This runs
    before any write, so a refusal can be asserted against a row that is
    UNCHANGED — one that fired after the name was already saved would leave the
    customer half-edited while the response still read *refused*
    (`portal_self_service.refuse_uneditable` learned this first).
    """
    fe: list[dict[str, Any]] = []
    for field in sorted(payload):
        if field in EDITABLE_FIELDS:
            continue
        if field in REFUSED_FIELDS:
            br_ref, reason = REFUSED_FIELDS[field]
            fe.append(
                _field_error(
                    field,
                    errors.VAL_FORMAT,
                    "customers.customer.edit.field_not_writable",
                    br_ref=br_ref,
                    reason=reason,
                )
            )
        else:
            fe.append(
                _field_error(field, errors.VAL_FORMAT, "customers.customer.edit.unknown_field")
            )
    _refuse(fe)


def _validate(customer: models.Customer, payload: dict[str, Any]) -> dict[str, Any]:
    """Clean the payload against the row's OWN kind, refusing everything at once.

    ⚠ **THE KIND ON THE ROW DECIDES, NOT A KIND IN THE PAYLOAD** — `kind` is in
    `REFUSED_FIELDS` and never arrives. `BR-CUS-1022`: a company is never asked
    for a driving licence and a person is never asked for a Tax ID, *refused BY
    NAME rather than dropped*.
    """
    fe: list[dict[str, Any]] = []
    cleaned: dict[str, Any] = {}
    kind = getattr(customer, "kind", None) or identity_match.KIND_PERSON
    allowed_ids = identity_match.KIND_IDENTIFIER_FIELDS.get(kind, ())
    dated = identity_match.KIND_DATED_FIELDS.get(kind, ())

    if "display_name" in payload:
        name = _clean(payload["display_name"])
        if name is None:
            # A customer with no name is not a correction, it is a deletion of
            # the one fact every screen in the product prints.
            fe.append(
                _field_error(
                    "display_name", errors.VAL_REQUIRED, "customers.customer.edit.name_required"
                )
            )
        else:
            cleaned["display_name"] = name

    if "external_ref" in payload:
        # NULLABLE on purpose — a customer created by the sign-up wizard has no
        # legacy id at all, and clearing a wrong one is a correction.
        cleaned["external_ref"] = _clean(payload["external_ref"])

    if "date_of_birth" in payload:
        if "date_of_birth" not in dated:
            # ⚠ `BR-CUS-1022`: a company has no date of birth — that is the
            # whole collision the rule resolves. Whether it gets the equivalent
            # (an incorporation date) is `OQ-1241`, still open.
            fe.append(
                _field_error(
                    "date_of_birth",
                    errors.VAL_FORMAT,
                    "customers.customer.edit.dob_not_for_company",
                    br_ref="BR-CUS-1022",
                )
            )
        else:
            cleaned["date_of_birth"] = _date(payload["date_of_birth"], fe)

    for field in IDENTIFIER_FIELDS:
        if field not in payload:
            continue
        if field not in allowed_ids:
            fe.append(
                _field_error(
                    field,
                    errors.VAL_FORMAT,
                    "customers.customer.edit.identifier_wrong_kind",
                    br_ref="BR-CUS-1022",
                    kind=kind,
                )
            )
            continue
        cleaned[field] = _clean(payload[field])

    if "email" in payload:
        cleaned["email"] = _clean(payload["email"])

    if "contact_by" in payload:
        contact_by = _clean(payload["contact_by"])
        if contact_by is not None and contact_by not in models.CONTACT_BY:
            fe.append(
                _field_error(
                    "contact_by",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "customers.serviceRequest.contactByUnknown",
                )
            )
        else:
            cleaned["contact_by"] = contact_by

    _refuse(fe)
    return cleaned


def _date(value: Any, fe: list[dict[str, Any]]) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        fe.append(
            _field_error("date_of_birth", errors.VAL_FORMAT, "customers.customer.edit.date_invalid")
        )
        return None


def _mask_blob(blob: dict[str, Any] | None) -> dict[str, Any] | None:
    """Replace every government identifier with its mask. `'123456789'` becomes
    `'•••••6789'` — enough to tell one identifier from another, never enough to
    be the identifier."""
    if not isinstance(blob, dict):
        return blob
    masked = dict(blob)
    for field in AUDIT_MASKED_FIELDS & set(masked):
        value = masked[field]
        masked[field] = crypto.mask(value) if isinstance(value, str) else value
    return masked


def _audit(
    actor: Any,
    action: str,
    entity_type: str,
    entity_id: Any,
    *,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    """Hard rule 7, with `BR-CUS-092(c)` applied at the boundary."""
    core_audit.write_row(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        before=_mask_blob(before),
        after=_mask_blob(after),
    )


def _customer_snapshot(customer: models.Customer) -> dict[str, Any]:
    """The before/after blob. CLEARTEXT for the identifiers — `_mask_blob` is
    what stands between this and `audit_log`, and it is applied once, at the
    boundary, so a new writer in this file gets it for free."""
    return {
        "display_name": customer.display_name,
        "external_ref": customer.external_ref,
        "date_of_birth": (
            customer.date_of_birth.isoformat() if customer.date_of_birth else None
        ),
        "ssn": customer.ssn,
        "driving_licence": customer.driving_licence,
        "phone": customer.phone,
        "tax_id": customer.tax_id,
        "custom_data": dict(customer.custom_data or {}),
    }


def _external_ref_is_taken(customer: models.Customer, value: str) -> bool:
    """`uq_customers_tenant_external_ref_ci` asked as a QUESTION rather than met
    as an exception, so the clerk gets a sentence naming the field."""
    return (
        models.Customer.objects.filter(tenant_id=customer.tenant_id)
        .exclude(pk=customer.pk)
        .annotate(ref_ci=Lower("external_ref"))
        .filter(ref_ci=value.lower())
        .exists()
    )


def _ref_taken_error(value: str) -> errors.ValidationError:
    return errors.ValidationError(
        errors.VAL_FORMAT,
        message_key="customers.customer.edit.ref_taken",
        params={"external_ref": value},
        field_errors=[
            _field_error(
                "external_ref",
                errors.VAL_FORMAT,
                "customers.customer.edit.ref_taken",
                external_ref=value,
            )
        ],
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def update_customer(actor: Any, customer_id: Any, changes: Any) -> dict[str, Any]:
    """`PATCH /customers/{id}` — **BR-CUS-1054.** A partial payload; every field
    it does not own is refused BY NAME with the rule that owns it.

    Returns the customer row as `GET /customers/{id}` serves it, plus
    `accounts_updated` — how many accounts an email correction reached — because
    *four accounts updated* is a sentence a clerk can act on and *saved* is not.
    """
    from apps.customers import selectors

    if not isinstance(changes, dict):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="customers.customer.edit.payload_not_object"
        )
    reject_unknown(changes)

    tenant_id = _tenant_id()
    with transaction.atomic():
        customer = (
            models.Customer.objects.select_for_update()
            .filter(tenant_id=tenant_id, pk=customer_id)
            .first()
            if _looks_like_uuid(customer_id)
            else None
        )
        if customer is None:
            # 404-never-403 (HR-1/G4): from outside the tenant, an id that
            # exists elsewhere and one that does not are the same fact.
            raise errors.deny_as_not_found("BR-TEN-003")

        cleaned = _validate(customer, changes)
        email = cleaned.pop("email", None) if "email" in cleaned else None
        wants_email = "email" in changes
        # DEF-CUS-10253 — the same reach as the email, one more contact column.
        contact_by = cleaned.pop("contact_by", None) if "contact_by" in cleaned else None
        wants_contact_by = "contact_by" in changes
        # CR-161-BRC10 W4 — merged, never replaced: a stored answer this dialog
        # does not draw is kept, a blank clears its key. Refused keyed
        # `custom_data.<key>` (BR-SHL-037) before anything is written.
        custom = (
            seams.validate_custom_data(
                "customers",
                changes.get(CUSTOM_FIELDS_KEY) or {},
                screen=CUSTOM_SCREEN,
                existing=dict(customer.custom_data or {}),
            )
            if CUSTOM_FIELDS_KEY in changes
            else None
        )

        before = _customer_snapshot(customer)
        fields: list[str] = []

        for field in PLAIN_FIELDS:
            if field not in cleaned:
                continue
            if getattr(customer, field) != cleaned[field]:
                setattr(customer, field, cleaned[field])
                fields.append(field)

        if custom is not None and custom != dict(customer.custom_data or {}):
            customer.custom_data = custom
            fields.append(CUSTOM_FIELDS_KEY)

        for field in IDENTIFIER_FIELDS:
            if field not in cleaned:
                continue
            if getattr(customer, field) == cleaned[field]:
                continue
            # ⚠ **THE ONE WRITER.** `set_identifier` sets the ciphertext AND its
            # blind-index token together; assigning the column directly here
            # would leave the index pointing at the OLD value and the customer
            # unfindable by the number just corrected, with every read-back test
            # still green.
            identity_match.set_identifier(customer, field, cleaned[field])
            fields.append(field)
            fields.append(identity_match.BIDX_COLUMN[field])

        if fields:
            if "external_ref" in fields and customer.external_ref:
                if _external_ref_is_taken(customer, customer.external_ref):
                    raise _ref_taken_error(customer.external_ref)
            # ⚠ **HARD-WON LAW 14 — THE SAVEPOINT IS NOT THE TIDY OPTION, IT IS
            # THE ONLY ONE.** `uq_customers_tenant_external_ref_ci` can still be
            # taken between the check above and this save by a sibling clerk. On
            # PostgreSQL the failed INSERT aborts the WHOLE transaction, so a
            # bare `except IntegrityError` would leave every later statement
            # raising `InFailedSqlTransaction` and the work lost at COMMIT — and
            # **the suite would never show it**, because
            # `config/settings/test.py` hardcodes in-memory SQLite, which has no
            # aborted-transaction state. The nested `atomic()` is a SAVEPOINT:
            # it rolls back to just before the save and the outer transaction
            # survives to raise a sentence the clerk can read.
            try:
                with transaction.atomic():
                    customer.save(update_fields=[*dict.fromkeys(fields), "updated_at"])
            except IntegrityError as exc:
                if customer.external_ref and "external_ref" in str(exc):
                    raise _ref_taken_error(customer.external_ref) from exc
                raise
            _audit(
                actor,
                "customer.updated",
                "customer",
                customer.pk,
                before=before,
                after=_customer_snapshot(customer),
            )

        touched = _write_email(actor, tenant_id, customer, email) if wants_email else []
        if wants_contact_by:
            for account_id in _write_contact_by(actor, tenant_id, customer, contact_by):
                if account_id not in touched:
                    touched.append(account_id)
        # ⊕ PO 2026-10-22 — the tick box. Last, so every refusal above has
        # already had its say, and inside the same transaction, so a refusal
        # here takes the contact write back with it.
        sign_in_moved = (
            move_sign_in(actor, tenant_id, customer.pk, email if wants_email else None)
            if changes.get(SIGN_IN_FLAG) is True
            else False
        )

    row = selectors.customer_detail(customer.pk) or {}
    return {
        **row,
        "accounts_updated": len(touched),
        "account_ids": touched,
        "portal_sign_in_moved": sign_in_moved,
    }


def _write_email(
    actor: Any, tenant_id: Any, customer: models.Customer, email: str | None
) -> list[str]:
    """The contact email, on EVERY account this customer holds.

    ⚠ **ONE SAVE REACHES EVERY ACCOUNT, AND THAT IS DELIBERATE RATHER THAN
    CONVENIENT** (`BR-CUS-054`, and `US-CWP-028` TC-10 settled the same question
    from the customer's side). `contacts` hangs off the ACCOUNT, so a landlord
    with four accounts has four contact rows; a save that fixed one would leave
    three bills going to the old address and nobody could tell which.

    ⚠ **A MISSING CONTACT ROW IS CREATED, NOT REFUSED.** *There is nowhere to
    put the email* is not an answer a clerk can act on. `full_name` comes from
    the customer's own `display_name` and never from the payload, so this path
    can never become a second way to set a name.

    ⚠ **NO PORTAL CREDENTIAL MOVES HERE.** `apps/portal`'s `email` is the
    sign-in identifier and belongs to another module (B2 §2). It follows only
    when the clerk ticks for it, and then through `move_sign_in` (PO
    2026-10-22, `OQ-CUS-12350` closed).
    """
    links = models.CustomerAccount.objects.filter(
        tenant_id=tenant_id, customer=customer
    ).select_related("account")
    touched: list[str] = []
    for link in links:
        account = link.account
        row = (
            models.Contact.objects.filter(
                tenant_id=tenant_id, account=account, deleted_at__isnull=True, is_primary=True
            )
            .order_by("created_at")
            .first()
        )
        created = False
        if row is None:
            row = models.Contact(
                tenant_id=tenant_id,
                account=account,
                full_name=customer.display_name or "",
            )
            created = True
        before = {"email": row.email}
        if row.email == email and not created:
            continue
        row.email = email
        row.save()
        _audit(
            actor,
            "customer.contact_email.corrected",
            "contact",
            row.pk,
            before=None if created else before,
            after={"email": row.email, "account_id": str(account.pk)},
        )
        touched.append(str(account.pk))
    return touched


def _write_contact_by(
    actor: Any, tenant_id: Any, customer: models.Customer, contact_by: str | None
) -> list[str]:
    """*Contact by*, on the primary contact of EVERY account this customer
    holds — `_write_email`'s reach and reasoning, for `DEF-CUS-10253`. A
    missing contact row is created with the customer's own name."""
    links = models.CustomerAccount.objects.filter(
        tenant_id=tenant_id, customer=customer
    ).select_related("account")
    touched: list[str] = []
    for link in links:
        account = link.account
        row = (
            models.Contact.objects.filter(
                tenant_id=tenant_id, account=account, deleted_at__isnull=True, is_primary=True
            )
            .order_by("created_at")
            .first()
        )
        created = row is None
        if row is None:
            row = models.Contact(
                tenant_id=tenant_id, account=account, full_name=customer.display_name or ""
            )
        if row.contact_by == contact_by and not created:
            continue
        before = None if created else {"contact_by": row.contact_by}
        row.contact_by = contact_by
        row.save()
        _audit(
            actor,
            "customer.contact_by.corrected",
            "contact",
            row.pk,
            before=before,
            after={"contact_by": row.contact_by, "account_id": str(account.pk)},
        )
        touched.append(str(account.pk))
    return touched


def _looks_like_uuid(value: Any) -> bool:
    from uuid import UUID

    try:
        UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return True


# ── Lifecycle ─────────────────────────────────────────────
# packet: BR-CUS-1054@this-commit (04-docs/05-modules/03-customers/02-business-rules.md)
#         + BR-CUS-054 + BR-CUS-092(c) + BR-CUS-1020 + BR-CUS-1022 + BR-CWP-026 verbatim
#         + CLAUDE.md hard rules 1/4/7/8 + hard-won law 14
#         ⚠ NO `US-XXX-###@<hex>` STAMP AND NONE IS INVENTED — `CR-094-BRC01` allocates no story ids, and minting one to satisfy `G01`'s regex would put a citation in the tree that resolves to nothing. Same posture as `apps/customers/close_out.py` and `CustomersListPage.tsx`
# generated: 2026-09-13 by the BR-CUS-1054 build lane
# checklist: A✔ B✔ C✔ D✔(apps/customers/api.py) E✔(the customers list row action) F✔ G✔ H=n/a(no money column is written here)
# gates: pytest tests/test_br_cus_1054_customer_edit.py · G32 (every message_key resolves in all eleven catalogues)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

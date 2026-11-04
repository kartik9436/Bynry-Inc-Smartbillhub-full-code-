# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-013 (EP-CWP-04) — About you: a form that survives a closed
#           tab, saved from the first keystroke, carrying no reference.
#           Screens: CWP-047 · CWP-008 (step 1's address) · CWP-009 (step 4)
# Rules:    US-CWP-013 §2 (*"A draft holds **no allocated number** until
#           submit"* — blueprint P33) · TC-1 (close the tab, come back, it is
#           all there) · TC-3 (a start date must be at least three working days
#           out) · TC-4 (a business is identified by company name and tax ID
#           rather than date of birth) · TC-5 (submit with the address step
#           incomplete is refused, naming the step, and the draft is KEPT) ·
#           TC-6 (a draft started on one tenant is not found on another) ·
#           BR-CWP-026 (a public form may create work and may never change an
#           account) · BR-CWP-031 (application matching MAY use date of birth)
# Tests:    06-backend/tests/test_us_cwp_013_about_you.py TC-1..TC-7
# Impacts:  apps/portal/write_points.py (MODULE_WRITE_TABLES declares that this
#           file writes PortalApplicationDraft and — from CR-158-BRC10,
#           2026-10-01 — PortalApplicationDocument, the applicant's attached
#           files; nothing else. G81 clause 3 lets it write, G84 says what) ·
#           apps/portal/services.py (submit) · apps/portal/guest_api.py
# ───────────────────────────────────────────────────────
"""THE DRAFT — the only thing on the guest surface that is written before
anybody has decided anything, and the only file besides `services.py` and the
back office that writes a portal row.

⚠ **WHY IT MAY WRITE, STATED HERE AS WELL AS IN THE REGISTER.** `BR-CWP-001`
caps the portal at four kinds of record — a payment, a service request, a meter
reading, a preference — and **a draft is none of them, because a draft is not a
record**. It is the applicant's own unsent form: it holds nothing the utility
has agreed to, it carries no reference, it changes no account, and it is
readable only by whoever holds its link. `write_points.py` declares this file's
allowance and names the ONE model it may touch; `G84` refuses any other model
written from here, so the allowance cannot quietly widen into a second billing
system one reasonable-looking commit at a time — which is the failure `CR-068`
§13 says a person cannot hold.

⚠ **AND WHY IT IS NOT A `service_requests` ROW IN THE `draft` STATE**, which is
what `03-field-map.md` and `US-CWP-013` §5 both say. `BR-CUS-093` (PO ruling
2026-08-24) numbers every service request AT CREATION, inside `create_request`'s
own transaction. A portal draft written that way is numbered on the applicant's
first keystroke and every abandoned half-typed form lands on the clerk's
worklist with a reference nobody was shown — the exact opposite of *"no promise
has been made"*. `models.PortalApplicationDraft` carries the full reasoning.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from apps.portal import models
from apps.portal.seams import customers_seam, metering_seam, tenancy_seam
from core import audit as core_audit
from core import errors

#: `US-CWP-013` TC-3 — *"at least three working days from today"*. The same
#: number `availability.WORKING_DAYS_TO_CONNECT` puts on the screen; imported
#: rather than re-typed so the promise and the refusal cannot drift.
from apps.portal.availability import WORKING_DAYS_TO_CONNECT  # noqa: E402

#: What a caller may put in a draft. Anything else is refused BY NAME rather
#: than dropped — a silently dropped field is a form that says it saved and did
#: not, which is the shape of half the defects this repository has filed.
DRAFT_FIELDS: frozenset[str] = frozenset(
    {
        "address_as_given",
        "address_unit_as_given",
        # DEF-CWP-9817 — the town and ZIP step 1 now asks, as the blueprint
        # draws them (p31). What the applicant TYPED (`BR-CUS-1091`).
        "address_city_as_given",
        "address_postal_code_as_given",
        "service_codes",
        "applicant_kind",
        "first_name",
        "last_name",
        "company_name",
        "email",
        "phone",
        "date_of_birth",
        "tax_id",
        "requested_start",
        # DEF-CWP-9818 — the applicant's category pick on step 3, as CODES
        # (PO ruling 2026-10-06, option b). Judged in `save_draft`.
        "account_type_code",
        "account_subtype_code",
        # DEF-CWP-9163 — *"Mailing address, if different"* (wireframe s17).
        "mailing_same_as_service",
        "mailing_line1",
        "mailing_line2",
        "mailing_city",
        "mailing_state",
        "mailing_postal_code",
        # `CR-161-BRC10` W7 — the answers to the utility's own questions, one
        # blob per record type. Judged in `save_draft` (it needs the stored
        # blob to merge into), never in `_clean`.
        "custom_data",
        # DEF-CUS-10225 — Move-in's fields, asked in Move-in's order (PO
        # 2026-10-18, image `04-portal.png`). Judged in `_clean`.
        "contact_by",
        "ssn_last4",
        "co_applicant",
        "co_applicant_name",
        "co_applicant_relationship",
        "co_applicant_phone",
        "co_applicant_email",
        "co_applicant_date_of_birth",
        "paperless",
        "text_reminders",
        "preferred_language",
    }
)

#: DEF-CUS-10225 — `customers.models.CONTACT_BY`, the one list *Contact by*
#: picks from on every screen. Restated rather than imported: the portal reads
#: the customers module only through its seam, and a test pins the two lists
#: equal (`test_def_cus_10250_portal_apply`).
CONTACT_BY = ("email", "text", "phone", "letter")
#: DEF-CUS-10257 — the co-applicant's *Relationship*, as Move-in's co-owner card
#: offers it (`CoOwnerCards.RELATIONSHIPS` on the screen; the request stores the
#: CODE and Move-in names it from its own catalogue). Free text reached that
#: card as a raw key, so the portal offers the same four and refuses any other.
RELATIONSHIPS = ("spouse", "partner", "family", "other")
#: The last four of an SSN — four digits, nothing else (PO 2026-10-18).
SSN_LAST4_RE = re.compile(r"^\d{4}$")
#: The same shape `tenancy.services._EMAIL_RE` accepts — something @ something
#: dot something. A FORMAT check, as Move-in's; never a deliverability one.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def phone_ok(value: str) -> bool:
    """A US phone number: ten digits once the punctuation is gone, or eleven
    starting with the country code 1 — Move-in's own check."""
    digits = re.sub(r"\D", "", value)
    return len(digits) == 10 or (len(digits) == 11 and digits.startswith("1"))

#: The five parts of a mailing address, in the order an envelope reads them.
MAILING_FIELDS = (
    "mailing_line1",
    "mailing_line2",
    "mailing_city",
    "mailing_state",
    "mailing_postal_code",
)
#: What an unticked *Same as the service address* must carry before Send —
#: everything but the unit line, which most addresses do not have.
MAILING_REQUIRED = ("mailing_line1", "mailing_city", "mailing_state", "mailing_postal_code")
#: Five digits or ZIP+4 — the kit's own `US_ZIP` (`UsAddressFields.tsx`), so the
#: box and the refusal cannot disagree about what a ZIP is.
US_ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")


def _flag(value: Any) -> bool:
    """A tick box's answer. `"false"`, `"0"`, `"off"` and `""` are no."""
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() not in ("", "0", "false", "no", "off")

KIND_PERSON = "person"
KIND_BUSINESS = "business"
APPLICANT_KINDS = (KIND_PERSON, KIND_BUSINESS)

#: A token is the capability that opens a draft, so it is checked for SHAPE
#: before it is used as a key: 16–128 characters of url-safe text. A browser's
#: `crypto.randomUUID()` is 36 of them and 122 bits of entropy.
TOKEN_RE = re.compile(r"^[A-Za-z0-9._~-]{16,128}$")

_MAX_TEXT = 500


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:_MAX_TEXT] or None


def _date(value: Any, field: str) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="portal.application.dateNotUnderstood",
            params={"field": field},
        ) from None


def earliest_start(today: date) -> date:
    """The first date service may be asked for — `US-CWP-013` TC-3.

    **Working days, counted the way a person counts them:** Saturdays and
    Sundays are skipped. Public holidays are NOT skipped here, and that is a
    stated boundary rather than an oversight — `tenancy.HolidayCalendar` holds
    the utility's own closures and `BR-CWP-096` reads it, which is wave D's
    task. Until it lands, the earliest date this refuses is never LATER than
    the true one, so the refusal can only ever be too permissive by a day and
    never too strict; a clerk moves the date, and nobody is turned away.
    """
    remaining = WORKING_DAYS_TO_CONNECT
    cursor = today
    while remaining > 0:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            remaining -= 1
    return cursor


def _clean(payload: Any, *, today: date) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else dict(payload or {})
    unknown = set(data) - DRAFT_FIELDS
    if unknown:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="portal.application.fieldNotAccepted",
            params={"field": sorted(unknown)[0]},
        )
    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        if key == "custom_data":
            # Passed through untouched: `save_draft` judges it against the
            # stored answers it merges into (W7).
            cleaned[key] = value
        elif key in ("date_of_birth", "requested_start", "co_applicant_date_of_birth"):
            cleaned[key] = _date(value, key)
        elif key == "service_codes":
            cleaned[key] = [str(one)[:64] for one in (value or []) if str(one).strip()]
        elif key in ("mailing_same_as_service", "co_applicant"):
            cleaned[key] = _flag(value)
        elif key in ("paperless", "text_reminders"):
            # NULL = not set; a tick box's answer otherwise.
            cleaned[key] = None if value in (None, "") else _flag(value)
        else:
            cleaned[key] = _text(value)
    # DEF-CWP-9163 — a mailing address is checked for FORMAT as it is typed and
    # for COMPLETENESS only at Send (`missing_before_submit`), the same split the
    # kit's `UsAddressFields` draws: an empty box is fine, a malformed one is a
    # slip caught before it is printed on an envelope.
    state = cleaned.get("mailing_state")
    if state:
        code = tenancy_seam.us_state_code(state)
        if code is None:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="portal.application.mailingStateUnknown",
                params={"value": state},
            )
        cleaned["mailing_state"] = code
    zip_code = cleaned.get("mailing_postal_code")
    if zip_code and not US_ZIP_RE.match(zip_code):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="portal.application.mailingZipFormat"
        )
    # DEF-CWP-9817 — the SERVICE address's ZIP, the same shape and the same
    # sentence (*"Use 12345 or 12345-6789."* names no field, so one key serves
    # both boxes). Step 1 checks it before it is ever sent.
    service_zip = cleaned.get("address_postal_code_as_given")
    if service_zip and not US_ZIP_RE.match(service_zip):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="portal.application.mailingZipFormat"
        )
    # DEF-CUS-10225 — Move-in's format checks, as each box is left: a blank is
    # fine while typing (required binds at Send), a malformed value is a slip.
    contact_by = cleaned.get("contact_by")
    if contact_by is not None and contact_by not in CONTACT_BY:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="portal.application.contactByUnknown",
            params={"value": contact_by},
        )
    relationship = cleaned.get("co_applicant_relationship")
    if relationship is not None and relationship not in RELATIONSHIPS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="portal.application.relationshipUnknown",
            params={"value": relationship},
        )
    last4 = cleaned.get("ssn_last4")
    if last4 is not None and not SSN_LAST4_RE.match(last4):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="portal.application.ssnLast4Format"
        )
    for field in ("email", "co_applicant_email"):
        value = cleaned.get(field)
        if value is not None and not EMAIL_RE.match(value):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="portal.application.emailFormat",
                params={"field": field},
            )
    for field in ("phone", "co_applicant_phone"):
        value = cleaned.get(field)
        if value is not None and not phone_ok(value):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="portal.application.phoneFormat",
                params={"field": field},
            )
    kind = cleaned.get("applicant_kind")
    if kind is not None and kind not in APPLICANT_KINDS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="portal.application.applicantKindUnknown",
            params={"value": str(kind)},
        )
    start = cleaned.get("requested_start")
    if start is not None and start < earliest_start(today):
        # TC-3 — refused, and the sentence names the rule rather than the date,
        # because a person reading *"at least three working days from today"*
        # can act on it without doing the arithmetic themselves.
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="portal.application.startTooSoon",
            params={"days": WORKING_DAYS_TO_CONNECT},
        )
    return cleaned


def missing_before_submit(row: models.PortalApplicationDraft) -> list[str]:
    """Which steps are not finished — `US-CWP-013` TC-5.

    ⚠ **THE DRAFT IS KEPT.** A refusal here never deletes anything; it names
    the step and the applicant goes back to it with everything still typed.
    Returned as step keys the screen turns into its own words (B14 rule 35 — the
    catalogue is written in its own language, so the server sends a key and
    never a sentence).
    """
    missing: list[str] = []
    if not row.address_as_given:
        missing.append("address")
    if not row.service_codes:
        missing.append("services")
    if row.applicant_kind == KIND_BUSINESS:
        # TC-4 — a business is identified by company name and tax ID, and
        # asking it for a date of birth would be asking a company when it was
        # born.
        if not row.company_name:
            missing.append("company_name")
        if not row.tax_id:
            missing.append("tax_id")
    else:
        if not row.first_name or not row.last_name:
            missing.append("name")
    # ⚠ **EMAIL IS OPTIONAL SINCE 2026-10-18 — Move-in's rule everywhere**
    # (decision log *"CUSTOMER DATA AND UI CONSISTENT ACROSS THE CREATE
    # SCREENS"*: phone required for a person, email optional — *"portal email
    # becomes optional"*). The mobile number is still required: it is how the
    # utility reaches somebody it has never met (`US-CWP-007` TC-4's reason).
    if not row.phone:
        missing.append("contact")
    # ⚠ **THE CATEGORY IS NO LONGER ASKED HERE — PO 2026-10-18, *"this is
    # correct"*** to *"the portal form does not ask the customer for internal
    # classifications … staff set the category when they review the request,
    # and it is required before the request can be approved"*. This read
    # `missing.append("category")` under `DEF-CWP-9818` (PO 2026-10-06 (b)),
    # which today's ruling supersedes; the refusal moved to the APPROVE door
    # (`service_request_service._refuse_unless_approvable`).
    # DEF-CUS-10225 — a ticked *Add a co-applicant* must name them (the card
    # draws Full name with the asterisk).
    if row.co_applicant and not row.co_applicant_name:
        missing.append("co_applicant")
    # DEF-CWP-9163 — an unticked *Same as the service address* is a promise of
    # somewhere else to send the bill, so it must say where before it is sent.
    if not row.mailing_same_as_service and any(
        not getattr(row, field) for field in MAILING_REQUIRED
    ):
        missing.append("mailing")
    if not row.requested_start:
        missing.append("start_date")
    # `CR-161-BRC10` W7 — a field the utility asks on the portal AND marked
    # required holds Send until it is answered (*"Required means required only
    # where it's typed in"*). Named by the STEP its box is on: the property's
    # questions are on step 2 beside the start date, the applicant's on step 3
    # beside their name. Appended after the core steps, in this order, which
    # `ApplyForService.unfinished()` mirrors key for key.
    unanswered = tenancy_seam.application_unanswered(row.tenant_id, row.custom_data)
    if "customers" in unanswered or "accounts" in unanswered:
        missing.append("your_questions")
    if "premises" in unanswered:
        missing.append("property_questions")
    return missing


def draft_row(tenant_id: Any, token: Any) -> models.PortalApplicationDraft | None:
    """The draft this token opens, within THIS tenant and no other.

    ⚠ **TC-6 IS THE DATABASE'S, NOT THIS FUNCTION'S.** A Pine Hill draft opened
    under Oak Ridge is not found because RLS makes the row invisible (migration
    0004); the tenant predicate here is the second lock and not the only one.
    """
    if not TOKEN_RE.match(str(token or "")):
        return None
    return models.PortalApplicationDraft.objects.filter(
        tenant_id=tenant_id, token=str(token)
    ).first()


def _stamp_visit(draft_id: Any) -> None:
    """The applicant came back — restart the 30 days (PO ruling 2026-10-02).

    PO, verbatim: *"Delete it 30 days after her last visit … If she returns on
    20 October, the 30 days start again."* Called on every act that IS a
    return: opening the link, saving, adding or removing a file.
    `draft_cleanup.py` reads the column this writes.

    ⚠ **`.update()`, NOT `.save()`, AND ONLY ON AN UNSENT DRAFT.** A save would
    move `updated_at` too, and opening a form changes nothing in it; and a sent
    draft is frozen (`BR-CWP-028`), so a visit to its link stamps nothing.
    """
    models.PortalApplicationDraft.objects.filter(
        pk=draft_id, submitted_at__isnull=True
    ).update(last_visited_at=timezone.now())


def open_draft(tenant_id: Any, token: Any) -> models.PortalApplicationDraft | None:
    """`GET /portal/public/applications/{token}` — the applicant opening their
    own link. The draft, or `None`; and the visit is recorded.

    ⚠ **A READ THAT WRITES, AND IT HAS TO.** The ruling counts a RETURN, not an
    edit: Maria who opens her link on 20 October, reads it and closes the tab
    has come back, and her 30 days start again. The guest edge may not write
    (`G81`), so the stamp is made here, in the one file allowed to write a
    draft.
    """
    row = draft_row(tenant_id, token)
    if row is not None and row.submitted_at is None:
        _stamp_visit(row.pk)
        row.refresh_from_db(fields=["last_visited_at"])
    return row


def save_draft(
    tenant_id: Any, token: Any, payload: Any, *, today: date | None = None
) -> models.PortalApplicationDraft:
    """`PUT /portal/public/applications/{token}` — upsert, from the first
    keystroke, and **no reference is allocated** (`US-CWP-013` §2).

    A draft that has already been sent is FROZEN: the row records what was
    submitted, and letting the browser keep writing to it would let somebody
    edit an application a clerk is already reading.
    """
    on = today or date.today()
    if not TOKEN_RE.match(str(token or "")):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="portal.application.linkNotUnderstood"
        )
    cleaned = _clean(payload, today=on)
    with transaction.atomic():
        row = (
            models.PortalApplicationDraft.objects.select_for_update()
            .filter(tenant_id=tenant_id, token=str(token))
            .first()
        )
        if row is not None and row.submitted_at is not None:
            raise errors.BizError(
                errors.BIZ_IMMUTABLE,
                br_ref="BR-CWP-028",
                message_key="portal.application.alreadySent",
            )
        if row is None:
            row = models.PortalApplicationDraft(tenant_id=tenant_id, token=str(token))
        if "custom_data" in cleaned:
            # `CR-161-BRC10` W7 — judged against ONLY the fields this utility
            # asks on the portal, and MERGED into what is stored, so a save
            # from step 2 does not wipe what step 3 typed. Nothing is required
            # while typing; Send is where required binds (`missing_before_submit`).
            cleaned["custom_data"] = tenancy_seam.clean_application_custom_answers(
                tenant_id, cleaned["custom_data"], existing=row.custom_data, require=False
            )
        for key, value in cleaned.items():
            setattr(row, key, value)
        if "account_type_code" in cleaned or "account_subtype_code" in cleaned:
            # DEF-CWP-9818 — judged against the SAME offered list the screen
            # was drawn from (the customers module's own), after the merge, so
            # a sub-category is always checked against the category it is under.
            problem = customers_seam.portal_category_problem(
                row.account_type_code, row.account_subtype_code
            )
            if problem is not None:
                raise errors.ValidationError(
                    errors.VAL_UNKNOWN_LOOKUP,
                    message_key=(
                        "portal.application.categoryNotOffered"
                        if problem == "category"
                        else "portal.application.subcategoryNotOffered"
                    ),
                )
        # A save is a visit (PO ruling 2026-10-02) — the 30 days restart.
        row.last_visited_at = timezone.now()
        if {"address_as_given", "address_city_as_given", "address_postal_code_as_given"} & set(
            cleaned
        ):
            # Re-resolved HERE rather than handed over by the browser: the
            # availability answer carries no premises id, deliberately
            # (`availability.py`), so nothing a stranger can edit decides which
            # address this application is against. DEF-CWP-9817 — on street,
            # town AND ZIP, through the staff side's own matcher.
            found = (
                metering_seam.find_premises_by_parts(
                    tenant_id,
                    row.address_as_given,
                    city=row.address_city_as_given,
                    postal_code=row.address_postal_code_as_given,
                )
                if row.address_as_given
                else None
            )
            row.matched_premises_id = found["id"] if found else None
        row.save()
    return row


def place_for(tenant_id: Any, premises_id: Any, unit_label: Any) -> dict[str, Any] | None:
    """`CR-200-BRC10` S9 — `{premises_id, unit_id}` a portal request is linked
    to, worked out ON THE SERVER, or None when nothing is held.

    `premises_id` is one this server matched itself from street, town and ZIP
    (never a value a browser sent — no id travels on the guest surface). The
    unit is the one whose LABEL the applicant picked (`unit_matching_label`);
    at a premises with exactly one live unit — a house — that unit is the only
    answer and is linked without asking, which is what the Approve window's
    *Unit* row needs. At a building with several and no label that matches
    (*Mine isn't listed*), only the premises is linked and the typed label
    stays on the request as said (`address_unit_as_given`).
    """
    if not premises_id:
        return None
    if metering_seam.premises_by_id(tenant_id, premises_id) is None:
        return None
    labels = metering_seam.unit_labels_to_choose(tenant_id, premises_id)
    unit = None
    if len(labels) == 1:
        unit = metering_seam.unit_matching_label(tenant_id, premises_id, labels[0])
    elif labels and str(unit_label or "").strip():
        unit = metering_seam.unit_matching_label(tenant_id, premises_id, unit_label)
    return {"premises_id": str(premises_id), "unit_id": unit["id"] if unit else None}


def place_from_parts(
    tenant_id: Any, street: Any, *, city: Any = None, postal_code: Any = None, unit_label: Any = None
) -> dict[str, Any] | None:
    """`place_for`, from typed parts — *Ask us for something* (PO A): a picked
    suggestion's street, town and ZIP are re-matched here exactly as Start
    service's check does; a typed address nobody holds is None, and the request
    is still accepted as typed (`BR-CUS-070`)."""
    if not str(street or "").strip() or not (str(city or "").strip() or str(postal_code or "").strip()):
        return None
    found = metering_seam.find_premises_by_parts(
        tenant_id, str(street).strip(), city=city, postal_code=postal_code
    )
    return place_for(tenant_id, found["id"], unit_label) if found else None


# ═══════════════════════════════════════════════════════════════════════════
# CR-158-BRC10 — THE APPLICANT'S DOCUMENTS (PO 2026-10-01; DF-4 superseded for
# the new-service request ONLY)
# ═══════════════════════════════════════════════════════════════════════════
#
# PO, verbatim: *"you need to allow customer to upload documents and save those
# document to server for that Utility - and then clark should able to view
# those document in new request"*.
#
# ⚠ **THIS FILE MAY WRITE `PortalApplicationDocument` AND THAT IS DECLARED IN
# `write_points.MODULE_WRITE_TABLES`, WHICH `G84` READS.** A file on an unsent
# form is part of the form, exactly as the draft is: it holds nothing the
# utility has agreed to and nothing a clerk can see. It becomes a service
# request's document only at submit, through the CUSTOMERS module's own service
# (`service_request_documents.attach_from_portal`), never by this module
# writing a customers table.

#: The limits, as the screen states them and as this edge refuses them. The
#: model holds the figures; these are the names the rest of the file reads.
DOCUMENT_TYPES = models.PortalApplicationDocument.CONTENT_TYPES
MAX_DOCUMENT_BYTES = models.PortalApplicationDocument.MAX_BYTES
MAX_DOCUMENTS = models.PortalApplicationDocument.MAX_PER_DRAFT
#: What a refusal names — extensions, never media types (B14 rule 33: a person
#: acts on `PDF`, not on `application/pdf`).
DOCUMENT_EXTENSIONS = "PDF, JPG, PNG"

_MAX_NAME = 200

#: ⚠ **THE DOCUMENTS AN APPLICATION ASKS FOR — `US-CWP-014` §4, and ONE list
#: (`DEF-CWP-9167`, PO ruling 2026-10-02, option A: *"a separate attach row for
#: each requirement (Photo ID, Proof of address), so it's always clear what each
#: file is for"*).** Served to the screen on every draft read
#: (`selectors.draft_view`), so *We will need these from you* and the attach
#: rows are drawn from here and never from a second copy in the browser.
#:
#: ⚠ **WHY A CONSTANT AND NOT THE TENANT'S CHECKLIST.** A utility's own
#: required-document checklist (`BR-CUS-095`,
#: `service_request_document_requirements`) is keyed on the JOB a request
#: becomes, which a clerk decides after reading it; at the portal nobody has
#: decided that yet. These two are what the portal asks of every applicant, and
#: each maps to one of `BR-CUS-095`'s designed types at Send
#: (`customers.service_request_documents.PORTAL_REQUIREMENT_DOC_TYPES`), so the
#: clerk's checklist and the applicant's file meet on the request.
DOCUMENT_REQUIREMENTS: tuple[str, ...] = ("photo_id", "proof_of_address")


class DocumentRefused(Exception):
    """A **413** (too large) or **415** (not a PDF, JPG or PNG) — the two
    transport rows that have no catalog code, carried out to the edge with
    their status, exactly as `customers.service_request_documents.UploadRefused`
    does for the staff door."""

    def __init__(self, status: int, message_key: str, **params: Any) -> None:
        self.status = status
        self.message_key = message_key
        self.params = params
        super().__init__(f"{status} {message_key}")


def sniff(payload: bytes) -> str | None:
    """What these BYTES are — PDF, JPEG or PNG — or `None`.

    ⚠ **THE BROWSER'S `Content-Type` IS NEVER READ.** It is a claim a stranger
    makes about their own upload, and a renamed `.html` sent as `image/png`
    would otherwise be filed, served back to a clerk and opened in the staff
    app's own origin. The signature is the first bytes of the file itself:

      * PDF  — `%PDF-` (ISO 32000-1 §7.5.2);
      * PNG  — the eight-byte signature `89 50 4E 47 0D 0A 1A 0A`;
      * JPEG — `FF D8 FF`, the SOI marker and the first marker after it.
    """
    head = bytes(payload[:8])
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def _safe_name(name: Any) -> str:
    """The file's own name, trimmed to its last path segment.

    A browser sends a bare name, but nothing makes a stranger's client do so;
    `C:\\scans\\licence.pdf` and `../../licence.pdf` both become `licence.pdf`.
    """
    text = str(name or "").replace("\\", "/").split("/")[-1].strip().lstrip(".")
    text = "".join(ch for ch in text if ch.isprintable())
    return text[:_MAX_NAME] or "document"


def document_view(row: models.PortalApplicationDocument) -> dict[str, Any]:
    """One attached file, as the applicant sees it — name, type, size, when.

    `id` is the address of the remove control and the React key; it is never
    printed (B14 rule 31). The bytes are never served back to the guest edge:
    the applicant already holds them, and a read path for a stranger's upload
    is a read path somebody else's token could be guessed against.
    """
    return {
        "id": str(row.id),
        # DEF-CWP-9167 — which required document this is, or None (*Other*).
        "requirement": row.requirement,
        "name": row.name,
        "content_type": row.content_type,
        "size_bytes": row.size_bytes,
        "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
    }


def documents_of(row: models.PortalApplicationDraft) -> list[dict[str, Any]]:
    """The files on this draft, oldest first — never the bytes.

    `.defer("payload")`: a list of names must not drag up to 50 MB out of the
    database to print five lines.
    """
    return [
        document_view(one)
        for one in models.PortalApplicationDocument.objects.filter(
            tenant_id=row.tenant_id, draft_id=row.pk
        )
        .defer("payload")
        .order_by("uploaded_at", "id")
    ]


def _open_draft_or_refuse(tenant_id: Any, token: Any) -> models.PortalApplicationDraft:
    draft = draft_row(tenant_id, token)
    if draft is None:
        # The same answer as a token that never existed, and as another
        # utility's token (RLS) — existence must not leak (BR-TEN-003).
        raise errors.NotFoundError()
    if draft.submitted_at is not None:
        # A sent application is frozen; its documents went with it.
        raise errors.BizError(
            errors.BIZ_IMMUTABLE,
            br_ref="BR-CWP-028",
            message_key="portal.application.alreadySent",
        )
    return draft


def _too_large(name: str) -> DocumentRefused:
    return DocumentRefused(
        413,
        "portal.application.documentTooLarge",
        name=name,
        max_mb=MAX_DOCUMENT_BYTES // (1024 * 1024),
    )


def read_upload(upload: Any) -> tuple[str, str, bytes]:
    """ONE guest file, read and judged: its safe name, the media type its BYTES
    are, and the bytes — or the refusal, by the file's name.

    Not a PDF, JPG or PNG by its bytes → 415; over 10 MB → 413; empty or absent
    → required. Shared by the application's own upload door (`add_document`)
    and the Track page's reply to *Ask for more* (`DEF-CWP-9049`), so the two
    doors a stranger can hand the utility a file through cannot disagree about
    what a file is.
    """
    if upload is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="portal.application.documentMissing"
        )
    name = _safe_name(getattr(upload, "name", ""))
    size = getattr(upload, "size", None)
    # ⚠ THE SIZE IS CHECKED BEFORE THE BYTES ARE READ when the upload says how
    # big it is, so an 80 MB file is refused without being pulled into memory;
    # and checked again on what was actually read, because `size` is a claim.
    if isinstance(size, int) and size > MAX_DOCUMENT_BYTES:
        raise _too_large(name)
    payload = upload.read(MAX_DOCUMENT_BYTES + 1) if hasattr(upload, "read") else bytes(upload)
    if not payload:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="portal.application.documentEmpty",
            params={"name": name},
        )
    if len(payload) > MAX_DOCUMENT_BYTES:
        raise _too_large(name)
    media_type = sniff(payload)
    if media_type is None:
        raise DocumentRefused(
            415,
            "portal.application.documentTypeNotAllowed",
            name=name,
            allowed=DOCUMENT_EXTENSIONS,
        )
    return name, media_type, payload


def _requirement(value: Any) -> str | None:
    """`photo_id`, `proof_of_address`, or None — refused BY NAME otherwise, so a
    file is never filed against a requirement nobody asked for."""
    text = str(value or "").strip()
    if not text:
        return None
    if text not in DOCUMENT_REQUIREMENTS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="portal.application.documentRequirementUnknown",
            params={"value": text[:64]},
        )
    return text


def add_document(
    tenant_id: Any, token: Any, upload: Any, *, requirement: Any = None
) -> models.PortalApplicationDocument:
    """`POST /portal/public/applications/{token}/documents` — one file.

    Refused, BY THE FILE'S NAME, when it is not a PDF, JPG or PNG by its bytes
    (415), over 10 MB (413), empty, or the sixth on this application. Each
    refusal leaves the draft and every file already on it untouched.

    `requirement` (`DEF-CWP-9167`) says which of `DOCUMENT_REQUIREMENTS` the
    file meets; absent, it is an *Other* document.
    """
    draft = _open_draft_or_refuse(tenant_id, token)
    which = _requirement(requirement)
    name, media_type, payload = read_upload(upload)
    with transaction.atomic():
        # The draft row is locked so two uploads racing from two tabs cannot
        # both count four and both write the fifth.
        models.PortalApplicationDraft.objects.select_for_update().filter(pk=draft.pk).first()
        held = models.PortalApplicationDocument.objects.filter(
            tenant_id=tenant_id, draft_id=draft.pk
        ).count()
        if held >= MAX_DOCUMENTS:
            raise errors.ValidationError(
                errors.VAL_RANGE,
                message_key="portal.application.documentLimit",
                params={"name": name, "max": MAX_DOCUMENTS},
            )
        row = models.PortalApplicationDocument.objects.create(
            tenant_id=tenant_id,
            draft=draft,
            requirement=which,
            name=name,
            content_type=media_type,
            size_bytes=len(payload),
            payload=payload,
        )
        _stamp_visit(draft.pk)
    # Hard rule 7 names money; a file a stranger hands the utility is evidence,
    # and "who sent this, and when" is the question that follows it. No actor —
    # the applicant is not a user — and the DRAFT is named, never the token:
    # the token is the capability and is never written to a log.
    core_audit.write_row(
        action="portal.application_document.uploaded",
        entity_type="portal_application_document",
        entity_id=row.id,
        after={
            "draft_id": str(draft.pk),
            "name": name,
            "content_type": media_type,
            "size_bytes": len(payload),
            "requirement": which,
            "declared_content_type": str(getattr(upload, "content_type", "") or "")[:100],
        },
    )
    return row


def remove_document(tenant_id: Any, token: Any, document_id: Any) -> None:
    """`DELETE …/documents/{id}` — the applicant takes back a file before sending.

    A real delete, and that is the point of holding the bytes here rather than
    in the write-once store: nothing has been given to the utility yet.
    """
    draft = _open_draft_or_refuse(tenant_id, token)
    row = (
        models.PortalApplicationDocument.objects.filter(
            tenant_id=tenant_id, draft_id=draft.pk, pk=document_id
        )
        .defer("payload")
        .first()
    )
    if row is None:
        raise errors.NotFoundError()
    before = {"draft_id": str(draft.pk), "name": row.name, "size_bytes": row.size_bytes}
    row.delete()
    _stamp_visit(draft.pk)
    core_audit.write_row(
        action="portal.application_document.removed",
        entity_type="portal_application_document",
        entity_id=document_id,
        before=before,
    )


def document_file(tenant_id: Any, token: Any, document_id: Any) -> dict[str, Any]:
    """`GET …/documents/{id}/content` — the applicant opens THEIR OWN file
    (`DEF-CWP-9166`, PO 2026-10-02: *"document upload is working but user not
    able to view give view button"*).

    ⚠ **THE TOKEN IS THE CAPABILITY, AND THE FILE MUST BE ON THE DRAFT IT
    OPENS.** `document_view`'s docstring said the bytes were *never served back
    to the guest edge* because *"a read path for a stranger's upload is a read
    path somebody else's token could be guessed against"*. That is answered,
    not ignored: the file is found by draft AND id AND tenant, so the only way
    to read it is to hold the 122-bit token that already opens the whole form —
    the same secret that can already change it. Another draft's file, another
    utility's draft (RLS, migration `portal/0011`), a removed file and a SENT
    application (its files went to the utility and were deleted here) all
    answer the same 404, because existence must not leak (`BR-TEN-003`).

    Audited, one row per open, naming the draft and never the token.
    """
    draft = draft_row(tenant_id, token)
    row = None
    if draft is not None:
        try:
            row = models.PortalApplicationDocument.objects.filter(
                tenant_id=tenant_id, draft_id=draft.pk, pk=document_id
            ).first()
        except (ValueError, TypeError, DjangoValidationError):
            row = None
    if row is None:
        raise errors.NotFoundError()
    payload = bytes(row.payload)
    core_audit.write_row(
        action="portal.application_document.viewed",
        entity_type="portal_application_document",
        entity_id=row.id,
        after={"draft_id": str(draft.pk), "name": row.name, "bytes": len(payload)},
    )
    return {
        "payload": payload,
        # What the BYTES were found to be on arrival — never the browser's word.
        "content_type": row.content_type,
        "name": row.name,
        # Only the three sniffed types are ever stored (the table's CHECK), so
        # every one of them may be drawn by the browser's own viewer.
        "inline": row.content_type in DOCUMENT_TYPES,
    }


def staged_files(draft: models.PortalApplicationDraft) -> list[dict[str, Any]]:
    """Every file on this draft, WITH its bytes — read once, at submit, to hand
    to the customers module's own service."""
    return [
        {
            "id": one.id,
            "requirement": one.requirement,
            "name": one.name,
            "content_type": one.content_type,
            "payload": bytes(one.payload),
            "uploaded_at": one.uploaded_at,
        }
        for one in models.PortalApplicationDocument.objects.filter(
            tenant_id=draft.tenant_id, draft_id=draft.pk
        ).order_by("uploaded_at", "id")
    ]


def discard_staged(draft: models.PortalApplicationDraft) -> int:
    """Delete this draft's held files once the store has them.

    Called inside the submit's transaction, AFTER the hand-over: if the
    hand-over fails the whole submit rolls back and the files are still here.
    Returns how many were removed.
    """
    removed, _ = models.PortalApplicationDocument.objects.filter(
        tenant_id=draft.tenant_id, draft_id=draft.pk
    ).delete()
    return removed

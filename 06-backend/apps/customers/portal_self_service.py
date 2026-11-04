# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-028 (EP-CWP-06) — my details, the contact half. Screen:
#           CWP-024 · US-CWP-027 (EP-CWP-06) — add another account. CWP-020
# Rules:    BR-CWP-001 kinds ⑤ `contact_detail` and ⑥ `account_link` (the rule
#           moved from FOUR to SIX on 2026-09-04 — the fifth by PO ruling
#           `OQ-CWP-1562`, the sixth by `DEF-CWP-3768`) · BR-CWP-103 (the
#           portal's security lives AT THE DOOR; a signed-in customer is not
#           asked to prove themselves again to edit their own record) ·
#           BR-CWP-026 (the legal name and the account holder are REFUSED, with
#           a route into a request) · BR-CWP-086 (returned post clears when the
#           address is corrected) · BR-CWP-010 (the account set is intersected
#           IN THE QUERY, by the caller, and this file trusts nothing else) ·
#           BR-CWP-009 (the set grows only from a customer-to-account link) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · rule 7 (audit) ·
#           rule 8 (an address lives on `premises`; `kind='mailing'` is one of
#           its three named exceptions — where the BILL goes)
# Tests:    06-backend/tests/test_us_cwp_028_my_details.py ·
#           06-backend/tests/test_us_cwp_027_add_account.py
# Impacts:  apps/portal/services.py (the two public functions that call this) ·
#           apps/portal/write_points.py (the rows that declare them)
# ───────────────────────────────────────────────────────
"""The `customers` module's own door for the two writes the portal may make.

⚠ **THIS FILE EXISTS BECAUSE CROSS-MODULE WRITES ARE FORBIDDEN** (B2 §2, and
G81 clause 4 enforces the portal half). `apps/portal` may not touch `contacts`,
`addresses` or `customer_accounts`; it calls a named function here, and this
module writes its own tables. The portal's side of that is a CALL, which is why
`MODULE_WRITE_TABLES` does not need to grow.

⚠ **WHAT IS REFUSED HERE IS THE POINT OF THE FILE, AND IT IS REFUSED BY NAME.**
`BR-CWP-026`: the legal name and the account holder are NOT contact details.
They are what a deposit carry-forward and a duplicate check are decided on, so
a portal that rewrote them would put a money decision behind a form nobody
checked. `update_contact_details` accepts three fields and **rejects a fourth
by naming it**, rather than ignoring it — a silently dropped field is a screen
that says *saved* over a value that went nowhere (`DEF-632`'s lesson).

⚠ **ONE SAVE REACHES EVERY ACCOUNT THE LOGIN HOLDS** (`US-CWP-028` TC-10), and
that is deliberate rather than convenient. `contacts` and `addresses` hang off
the ACCOUNT, so Maria Alvarez with four accounts has four contact rows; a save
that fixed one would leave three bills going to the old email and she would
have no way to tell which. The screen states it; this function does it.

⚠ **AND IT SAYS SO ON THE ROWS IT DOES NOT FIND.** An account in the set with
no primary contact row gets one CREATED, because *"there is nowhere to put your
email"* is not an answer a customer can act on. An account with no mailing
address gets one created the same way, and only when a postal address was
actually given.
"""

from __future__ import annotations

import re
from typing import Any

from django.db import transaction

from apps.customers import models
from core import audit as core_audit
from core import errors

#: The three fields `BR-CWP-001` kind ⑤ names, and the whole of it.
EDITABLE_FIELDS: frozenset[str] = frozenset({"email", "phone", "postal"})

#: ⚠ **REFUSED BY NAME, NEVER IGNORED** (`BR-CWP-026`). Each maps to the
#: message key the screen turns into *ask us to change this* — a refusal that
#: names the field and offers the route, in the reader's own language (B14
#: rule 35), and never a silent drop.
REFUSED_FIELDS: dict[str, str] = {
    #: ⚠ **`legal_name` IS THE WORD THE CONTRACT PUBLISHES AND IT WAS THE ONE
    #: WORD MISSING** (CR-085 group I, 2026-09-08). `GET portal/my-details`
    #: answers `refused: ["legal_name", "account_holder"]`, so a client posting
    #: back the word it was handed got the generic *we cannot change that here*
    #: while the sentence written for exactly this refusal sat unused. Every
    #: other key here is a MODEL column; this one is the wire's, and the two
    #: vocabularies had never been checked against each other.
    "legal_name": "portal.myDetails.refused.name",
    "full_name": "portal.myDetails.refused.name",
    "last_name": "portal.myDetails.refused.name",
    "first_name": "portal.myDetails.refused.name",
    "display_name": "portal.myDetails.refused.name",
    "account_holder": "portal.myDetails.refused.holder",
    "customer": "portal.myDetails.refused.holder",
    "dob": "portal.myDetails.refused.identity",
    "gov_id_last4": "portal.myDetails.refused.identity",
    "ssn": "portal.myDetails.refused.identity",
}

#: `kind='mailing'` — hard rule 8's first named exception: where the BILL goes,
#: which for a landlord is a different building from any premises they hold.
#: ⚠ `kind='service'` is RETIRED and is never written here.
MAILING = "mailing"

#: The parts of a postal address this path may set. `line2` and `country` are
#: here because `DEF-2847` added the columns and nothing has ever been able to
#: fill them; a customer typing their own address is the first thing that can.
POSTAL_PARTS: tuple[str, ...] = ("line1", "line2", "city", "state", "postal_code", "country")


#: F-11 (decision log 2026-10-23, "Groups B and C: how they are built" point 10).
#: ⚠ **THESE ARE THE PORTAL'S EXISTING CHECKS, COPIED AND HELD EQUAL BY A TEST**
#: (`tests/test_def_cwp_f11_my_details_phone_zip.py`) — `apps.portal.applications`
#: `phone_ok` and `US_ZIP_RE` (Move-in's phone check; the kit's `US_ZIP`). They
#: are not imported because `customers` may not depend on `portal` (B2 §2);
#: they are copied rather than re-invented so a customer is never told a phone
#: is fine on the application and wrong on My details.
US_ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")


def phone_ok(value: str) -> bool:
    """Ten digits once the punctuation is gone, or eleven starting with 1."""
    digits = re.sub(r"\D", "", value)
    return len(digits) == 10 or (len(digits) == 11 and digits.startswith("1"))


def _refuse_bad_formats(phone: str | None, postal: dict[str, Any] | None) -> None:
    """F-11 — a malformed phone or ZIP is refused ON THE FIELD and never stored.

    Runs before any write, so a refusal leaves every account as it was. A
    BLANK ZIP passes: the mailing address is optional. A blank phone passes
    too, because a blank phone is a REMOVAL (see `update_contact_details`).
    Both problems are named at once, so the screen can mark both boxes.
    """
    problems: list[dict[str, Any]] = []
    if phone is not None and not phone_ok(phone):
        problems.append(
            {
                "field": "phone",
                "code": errors.VAL_FORMAT,
                "message_key": "portal.myDetails.phoneFormat",
                "params": {},
            }
        )
    zip_code = _clean((postal or {}).get("postal_code"))
    if zip_code is not None and not US_ZIP_RE.match(zip_code):
        problems.append(
            {
                "field": "postal_code",
                "code": errors.VAL_FORMAT,
                "message_key": "portal.myDetails.zipFormat",
                "params": {},
            }
        )
    if problems:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key=problems[0]["message_key"],
            params={},
            field_errors=problems,
        )


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def refuse_uneditable(payload: dict[str, Any]) -> None:
    """`BR-CWP-026` — a field outside the three is refused, and it is NAMED.

    ⚠ **THE ORDER MATTERS AND IT IS THE ONE THING TO GET RIGHT HERE.** This
    runs before any write, so `US-CWP-028` TC-2 can assert the stored name is
    UNCHANGED — a refusal that fired after the email was already saved would
    leave the account half-edited and the response would still read *refused*.
    """
    for field in sorted(payload):
        if field in EDITABLE_FIELDS:
            continue
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-026",
            message_key=REFUSED_FIELDS.get(field, "portal.myDetails.refused.unknown"),
            params={"field": field},
        )


@transaction.atomic
def update_contact_details(
    actor: Any,
    *,
    tenant_id: Any,
    account_ids: list[Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """`BR-CWP-001` kind ⑤ — the customer's own email, mobile and postal address.

    ⚠ **`account_ids` IS THE SESSION'S OWN SET AND IS NEVER TAKEN FROM A BODY**
    (`BR-CWP-010`). The caller has already intersected it in the query; this
    function filters on it AGAIN, because a write that trusts its caller's
    filtering is one refactor away from writing another customer's contact row.

    Returns what changed, per account, so the screen can say *four accounts
    updated* rather than *saved* — `US-CWP-028` TC-10 is a sentence a customer
    reads, not an implementation note.
    """
    refuse_uneditable(payload)
    ids = [str(one) for one in account_ids]
    if not ids:
        # A signed-in customer always holds at least one account; an empty set
        # here means the caller lost it, and writing nothing quietly would look
        # exactly like a successful save.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-010",
            message_key="portal.myDetails.noAccounts",
            params={},
        )

    email = _clean(payload.get("email"))
    phone = _clean(payload.get("phone"))
    postal = payload.get("postal") if isinstance(payload.get("postal"), dict) else None
    _refuse_bad_formats(phone, postal)
    # ⚠ **F-11 (PO 2026-10-23): AN EMPTIED PHONE BOX REMOVES THE PHONE.** It
    # used to mean *do not touch* (`_clean("")` is None), so a customer who
    # cleared her number was told *"Saved on 0 accounts"* and the number
    # stayed. A `phone` key that is PRESENT and blank is the removal; an
    # absent key still touches nothing.
    remove_phone = "phone" in payload and phone is None

    touched: list[str] = []
    removed_from: list[str] = []
    for account_id in ids:
        account = (
            models.Account.objects.filter(tenant_id=tenant_id, id=account_id)
            .only("id")
            .first()
        )
        if account is None:
            # ⚠ Tenant scoping is the QUERY's, not a check afterwards — an
            # account id from another tenant simply does not come back, and the
            # loop moves on rather than raising and telling a caller it exists.
            continue
        changed = _write_contact(
            actor, tenant_id, account, email=email, phone=phone, remove_phone=remove_phone
        )
        if changed == PHONE_REMOVED:
            removed_from.append(str(account_id))
        if postal is not None:
            changed = _write_address(actor, tenant_id, account, postal) or changed
        if changed:
            touched.append(str(account_id))
    # ⚠ The text-reminder SWITCH is not turned off (decision log 2026-10-23
    # point 10): the ruling TELLS her reminders stop, it does not change her
    # setting. `text_reminders_on` is what the screen needs to say so.
    reminders_on = bool(removed_from) and (
        models.Account.objects.filter(
            tenant_id=tenant_id, id__in=removed_from, sms_reminders=True
        ).exists()
    )
    return {
        "accounts_updated": len(touched),
        "account_ids": touched,
        "phone_removed": bool(removed_from),
        "text_reminders_on": reminders_on,
    }


#: What `CWP-025` may actually change, and it is THREE COLUMNS ON THE ACCOUNT.
#:
#: ⚠ **THERE IS NO PER-EVENT CUSTOMER PREFERENCE IN THIS PRODUCT AND ONE WAS
#: NOT INVENTED HERE (`DEF-CWP-3860`, `OQ-CWP-1660`).** `US-CWP-028` §5 maps the
#: grid onto the *"notification rule catalogue"*, which is
#: `notification_rules` — **the TENANT's row, one per event per tenant by unique
#: constraint**. A customer saving there would change what every other customer
#: of that utility receives. So the grid is built on the store that genuinely
#: holds a customer's own choice: `accounts.paperless` adds email,
#: `accounts.sms_reminders` adds text, and print is the floor underneath both.
DELIVERY_FIELDS: frozenset[str] = frozenset({"email_on", "text_on", "locale"})

#: ⚠ **REFUSED BY NAME, NEVER IGNORED** (`US-CWP-028` TC-3). *Post* is not a
#: setting a customer holds: `CHANNEL_FLOOR_BY_SOURCE` prints every customer
#: document whatever else is elected, so a payload asking to switch it off is
#: told so rather than being dropped into a screen that says *saved*.
REFUSED_DELIVERY_FIELDS: dict[str, str] = {
    "post_on": "portal.preferences.refused.post",
    "post": "portal.preferences.refused.post",
}


def update_delivery_preferences(
    actor: Any,
    *,
    tenant_id: Any,
    account_ids: list[Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """`BR-CWP-001`'s `preference` kind — how a customer wants to be reached.

    ⚠ **THESE COLUMNS ONLY EVER *ADD* A CHANNEL** (`BR-BIL-036`, and
    `accounts.paperless`'s own comment says it in as many words: *"a `paperless`
    account still gets its print row … these columns only ever ADD a channel"*).
    Switching both off does not stop a single letter; it stops the email and the
    text that ride alongside. The screen must say that, and `CWP-025` does.

    ⚠ **`account_ids` IS THE SESSION'S SET AND NEVER A BODY's** (`BR-CWP-010`),
    and one save reaches every account this login holds — the same posture
    `update_contact_details` takes, for the same reason: four accounts with four
    different answers to *how do you want your bills* is a state a customer can
    neither see nor fix.

    ⚠ **AND THE LANGUAGE IS THE ACCOUNT'S, NOT THE LOGIN'S.** `PortalCredential`
    carries no locale column and one was not added here — `preferred_language`
    is what the document renderer already reads (`BR-CUS-064`), so a customer
    choosing Spanish changes the language of the NEXT LETTER, which is what
    `US-CWP-028` TC-9 asks for.
    """
    named = [field for field in payload if field in REFUSED_DELIVERY_FIELDS]
    if named:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-NOT-024",
            message_key=REFUSED_DELIVERY_FIELDS[named[0]],
            params={"field": named[0]},
        )
    ids = [str(one) for one in account_ids]
    if not ids:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-010",
            message_key="portal.myDetails.noAccounts",
            params={},
        )
    unknown = [field for field in payload if field not in DELIVERY_FIELDS]
    if unknown:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="portal.preferences.unknownField",
            params={"field": unknown[0]},
        )

    touched: list[str] = []
    for account_id in ids:
        account = (
            models.Account.objects.filter(tenant_id=tenant_id, id=account_id)
            .only("id", "paperless", "sms_reminders", "preferred_language")
            .first()
        )
        if account is None:
            # Tenant scoping is the QUERY's — another tenant's id simply does
            # not come back, and the loop moves on rather than telling a caller
            # it exists.
            continue
        fields: list[str] = []
        was = {
            "paperless": account.paperless,
            "sms_reminders": account.sms_reminders,
            "preferred_language": account.preferred_language,
        }
        if "email_on" in payload and bool(payload["email_on"]) != account.paperless:
            account.paperless = bool(payload["email_on"])
            fields.append("paperless")
        if "text_on" in payload and bool(payload["text_on"]) != account.sms_reminders:
            account.sms_reminders = bool(payload["text_on"])
            fields.append("sms_reminders")
        if "locale" in payload:
            wanted = _clean(payload["locale"])
            if wanted != account.preferred_language:
                account.preferred_language = wanted
                fields.append("preferred_language")
        if not fields:
            continue
        before = {field: was[field] for field in fields}
        account.save(update_fields=fields)
        # Hard rule 7 — every change names its actor, and the actor is the
        # CUSTOMER rather than a clerk (`BR-CWP-103`). `actor_user_id` stays
        # NULL and the payload names the person: see `_portal_actor`.
        core_audit.write_row(
            action="portal.preference.updated",
            entity_type="account",
            entity_id=account.pk,
            actor_user_id=None,
            before=before,
            after={
                **{field: getattr(account, field) for field in fields},
                "actor": _portal_actor(actor),
            },
        )
        # ⚖️ `DEF-RAT-9833` (PO ruling 4, 2026-10-06, reading (b)) — email
        # bills switched ON by the customer puts a Paperless discount the plan
        # carries in place for the next bill now; the actor is the customer, not
        # a staff user, so none is named (`source` says which door).
        if "paperless" in fields and account.paperless:
            from apps.customers import discounts as customer_discounts

            customer_discounts.settings_switched_on(None, account.pk, source="portal")
        touched.append(str(account_id))
    return {"accounts_updated": len(touched), "account_ids": touched}


#: What `_write_contact` answers when the change took a phone number AWAY —
#: truthy, so the caller still counts the account as touched (F-11).
PHONE_REMOVED = "phone_removed"


def _write_contact(
    actor,
    tenant_id,
    account,
    *,
    email: str | None,
    phone: str | None,
    remove_phone: bool = False,
) -> bool | str:
    if email is None and phone is None and not remove_phone:
        return False
    row = (
        models.Contact.objects.filter(
            tenant_id=tenant_id, account=account, deleted_at__isnull=True, is_primary=True
        )
        .order_by("created_at")
        .first()
    )
    created = False
    if row is None and email is None and phone is None:
        # A removal with nothing on file: there is no number to take away, and
        # no empty contact row is created just to say so.
        return False
    if row is None:
        # ⚠ CREATED rather than refused — see the module docstring. `full_name`
        # is required by the column and is NOT taken from the payload: it comes
        # from the account's own customer, so this path can never be a way to
        # set a name `BR-CWP-026` refuses.
        row = models.Contact(
            tenant_id=tenant_id, account=account, full_name=_name_on_file(tenant_id, account)
        )
        created = True
    before = {"email": row.email, "phone": row.phone}
    if email is not None:
        row.email = email
    if phone is not None:
        row.phone = phone
    elif remove_phone:
        row.phone = None
    after = {"email": row.email, "phone": row.phone}
    if not created and before == after:
        return False
    row.save()
    core_audit.write_row(
        action="portal.contact_detail.updated",
        entity_type="contact",
        entity_id=row.id,
        actor_user_id=None,  # see `_portal_actor` — a customer is not a User
        before=None if created else before,
        after={**after, "actor": _portal_actor(actor)},
    )
    if remove_phone and before.get("phone") and not row.phone:
        return PHONE_REMOVED
    return True


def _write_address(actor, tenant_id, account, postal: dict[str, Any]) -> bool:
    """The MAILING address — hard rule 8's *where the bill goes*.

    ⚠ **AND CORRECTING IT CLEARS THE RETURNED-POST FLAG** (`BR-CWP-086`). The
    banner exists to be acted on; leaving it up after the customer has done the
    one thing it asked for would teach them to ignore it.
    """
    parts = {key: _clean(postal.get(key)) for key in POSTAL_PARTS if key in postal}
    if not parts:
        return False
    row = (
        models.Address.objects.filter(
            tenant_id=tenant_id, account=account, kind=MAILING, deleted_at__isnull=True
        )
        .order_by("created_at")
        .first()
    )
    created = False
    if row is None:
        row = models.Address(tenant_id=tenant_id, account=account, kind=MAILING, line1="")
        created = True
    before = {key: getattr(row, key) for key in POSTAL_PARTS}
    for key, value in parts.items():
        setattr(row, key, value if key != "line1" else (value or ""))
    after = {key: getattr(row, key) for key in POSTAL_PARTS}
    if not created and before == after:
        return False
    row.save()
    _clear_returned_post(account, actor)
    core_audit.write_row(
        action="portal.contact_detail.updated",
        entity_type="address",
        entity_id=row.id,
        actor_user_id=None,  # see `_portal_actor`
        before=None if created else before,
        after={**after, "actor": _portal_actor(actor)},
    )
    return True


def _clear_returned_post(account, actor: Any = None) -> None:
    """`BR-CWP-086` — the customer corrected their address, so post stops being
    treated as coming back.

    ⚠ **REWRITTEN 2026-09-23 (`DEF-PAY-6342`).** This lowered the column with a
    bare `save()` — no audit row, and the account's open returned-post rows in
    payments left OPEN, so the clerk's needs-attention list went on showing an
    envelope the customer had already dealt with. Two acts now, each by the
    module that owns the table:

      * `bad_address.clear_bad_address` — customers' own column, audited, with
        the customer named in the payload (a portal customer is not a `User`,
        so `actor_user_id` stays NULL — `_portal_actor`'s rule);
      * payments' `resolve_open_returns` — every open return closed as
        `address_corrected`, dated with the tenant's business day (a clock read
        here would be the server's timezone, BR-TEN-043), with no staff user
        named for the same reason.

    ⚠ **IT NEVER STOPS A CUSTOMER SAVING THEIR ADDRESS.** Neither act can
    refuse on a normal account; payments being unpublished leaves the returns
    open on the clerk's list, which is visible, rather than failing the save.
    """
    from apps.customers import bad_address, payments_seam, seams

    context = {"actor": _portal_actor(actor)}
    bad_address.clear_bad_address(
        account.id, actor=None, via=bad_address.VIA_CUSTOMER_PORTAL, context=context
    )
    payments_seam.resolve_open_returns(
        account_id=account.id,
        resolution="address_corrected",
        resolved_on=seams.tenant_today(),
        actor=None,
        context={"via": bad_address.VIA_CUSTOMER_PORTAL, **context},
    )


def _name_on_file(tenant_id: Any, account) -> str:
    link = (
        models.CustomerAccount.objects.filter(tenant_id=tenant_id, account=account)
        .select_related("customer")
        .first()
    )
    name = getattr(getattr(link, "customer", None), "display_name", None)
    return str(name) if name else ""


def _portal_actor(actor: Any) -> dict[str, Any]:
    """WHO did it, for `audit_log` — and it is **not** `actor_user_id`.

    ⚠ **A PORTAL CUSTOMER IS NOT A `User` AND MUST NOT BE WRITTEN AS ONE.**
    `BR-CWP-004` keeps the two apart on purpose — *separate table, separate
    session, separate permission catalogue, not one table with a flag on it* —
    so there is no staff user id to put in that column, and inventing one would
    make a customer's edit indistinguishable from a clerk's in the one record
    that exists to tell them apart.

    `core.audit.write_row`'s own contract covers this case in as many words:
    *"who = actor_user_id (None = system job; name the job in the payload)"*.
    So `actor_user_id` stays NULL and the payload NAMES the customer and the
    session they were signed in on — which is what `US-CWP-028` TC-1 asks for
    (*an audit entry naming Maria Alvarez as the actor*) and is stronger than a
    user id, because it also says which device.
    """
    return {
        "portal_customer_id": str(getattr(actor, "customer_id", "") or "") or None,
        "portal_session_id": str(getattr(actor, "session_id", "") or "") or None,
        "channel": "customer_portal",
    }


# ═══════════════════════════════════════════════════════════════════════════
# `BR-CWP-001` kind ⑥ — the account link (US-CWP-027)
# ═══════════════════════════════════════════════════════════════════════════


def already_linked(tenant_id: Any, *, customer_id: Any, account_id: Any) -> bool:
    """`US-CWP-027` TC-4 — an account already in the set is refused as such."""
    return models.CustomerAccount.objects.filter(
        tenant_id=tenant_id, customer_id=customer_id, account_id=account_id
    ).exists()


@transaction.atomic
def link_account(actor: Any, *, tenant_id: Any, customer_id: Any, account_id: Any) -> dict[str, Any]:
    """One `customer_accounts` row, and **nothing else is written**.

    ⚠ **NOTHING IS COMBINED** (`BR-CWP-015`, `US-CWP-027` TC-7). No balance is
    merged, no invoice is created, no account is re-homed. The set is FLAT
    (`BR-CWP-013`) and `session.account_set` re-derives it on every request, so
    this row widens what one person may SEE and changes not one figure in the
    utility's books.

    ⚠ **AND IT CARRIES NO MATCH TIER.** `BR-CUS-089` stores the tier with its
    CONFIRMER, and the confirmer of a match is the human at the counter. Nobody
    was at a counter here: a customer answered a code that went to the contact
    already on the account. Writing a tier would attribute a staff judgment to
    a form, so the columns stay NULL and a deposit carry-forward still needs a
    person — which is the conservative half of `BR-CWP-103`, not a gap in it.
    """
    link, created = models.CustomerAccount.objects.get_or_create(
        tenant_id=tenant_id, customer_id=customer_id, account_id=account_id
    )
    core_audit.write_row(
        action="portal.account_link.created",
        entity_type="customer_account",
        entity_id=link.id,
        actor_user_id=None,  # see `_portal_actor`
        before=None,
        after={
            "customer_id": str(customer_id),
            "account_id": str(account_id),
            "actor": _portal_actor(actor),
        },
    )
    return {"linked": True, "created": created, "link_id": str(link.id)}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-028 + US-CWP-027@this-commit (EP-CWP-06 stories + BR-CWP-026/086/009/015 verbatim + OQ-CWP-1562's closure)
# generated: 2026-09-04 by the CR-068 wave G build lane
# checklist: A✔ B✔ C✔ D✔(apps/portal/services.py) E✔(CWP-024, CWP-020) F✔ G✔ H=n/a(no money column is written here)
# gates: G81 (the portal calls this, it does not write these tables) · G84 · pytest tests/test_us_cwp_028_my_details.py tests/test_us_cwp_027_add_account.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

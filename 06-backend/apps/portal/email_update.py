# ── Trace ──────────────────────────────────────────────
# Change:   CR-189-BRC10 (items 2–4) — "update your registered email" for a
#           customer who is LOCKED OUT of the portal. Screen: CWP-019U
#           (`/{tenant}/portal/update-email`).
# Rules:    decision log 2026-10-22 "Portal forgot-password: one message for
#           every address, plus a self-service 'update your registered email'
#           path" (items 3, 5, 6) · the same day's "…when nothing on file can be
#           reached, show 'Call the office'" (supersedes item 4) · "Account-access
#           emails are sent instantly" · "languages via template variants, and
#           'don't do any hardcoding'" · BR-CWP-030/031 (the three bill facts,
#           never DOB/SSN) · BR-CWP-023 (five tries, fifteen minutes) ·
#           BR-CWP-033 (a code goes only to a contact ALREADY on file) ·
#           BR-CWP-034 (no contact → dead end, never something weaker) ·
#           BR-CWP-035 (ten minutes) · BR-CWP-001 kind ⑤ `contact_detail`
#           (OQ-CWP-1562: the master record moves with the customer's email) ·
#           BR-CWP-102 (a portal file may write the portal's OWN auth rows) ·
#           CLAUDE.md hard rules 1 and 7
# Tests:    06-backend/tests/test_cr189_portal_update_email.py ·
#           test_cr189_portal_update_email_pg.py (PostgreSQL, law 14)
# Impacts:  apps/portal/email_update_api.py (its only caller) ·
#           write_points.py (this file's allowance) · credentials.py (reused,
#           not edited)
# ───────────────────────────────────────────────────────
"""🔒 THE LOCKED-OUT CUSTOMER'S EMAIL CHANGE — five steps, each one a door.

HUMAN-REVIEW-PENDING (CLAUDE.md 🔒 sensitive paths: this file decides which
address a password-reset link goes to). AI-authored 2026-10-22 under the PO
ruling of 2026-08-09; row in 12-governance/09-human-review-ledger.md.

WHAT A DEFEAT OF THIS FILE COSTS
--------------------------------
One customer's login. Somebody who gets an email changed here receives that
customer's reset link, so the guard is the same as enrolment's: **the three
facts printed on the bill, then a code to a contact already on file.** A stolen
bill on its own reaches a code the thief cannot read.

THE FIVE STEPS AND WHAT EACH REFUSES
------------------------------------
1. `find` — the three bill facts (`credentials.find_account`, the ONE matcher).
   A miss counts against this door's own lock: five tries, fifteen minutes
   (`lockout`'s BR-CWP-023 numbers). Every miss gets the same answer. A match
   returns the contacts on file MASKED and nothing else about the account.
   With no contact on file it dead-ends into *call the office*, with the
   utility's phone and hours read from Settings (PO 2026-10-22).
2. `send_code` — the person picks one MASKED option. The option is a keyed hash
   of the destination, so the browser never holds a phone number or an id.
   The code goes there through the enrolment code's own queue path.
3. `verify_code` — ten minutes, six tries, single use (`credentials.verify_code`).
4. `start_confirmation` — the new address gets a code. **The address is not
   stored.** The code is bound to it: the row holds `sha256(code + address)`, so
   only the same address and the same code together confirm. An address that
   is ANOTHER customer's login gets the identical answer and no code. Telling
   the two apart would let anybody holding a bill ask *"does this address bank
   online here?"*.
5. `confirm` — the email changes on the portal login AND on the customer's
   contact rows (the signed-in `contact_detail` door, reused). The old address
   is told. A reset link goes to the new one. With no login yet, the answer is
   `enrol` and the screen points to sign-up (decision log 2026-10-22,
   *"CR-189 judgments"*).

NOTHING HERE IS A SENTENCE. Every answer is a key the eleven catalogues word
(B14 rule 35). Email wording is the utility's own template (no fallback text).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.customers import models as customers_models
from apps.portal import credentials, lockout, models, selectors, services
from apps.portal.seams import notifications_seam, tenancy_seam
from core import audit

#: This door's own lock bucket. Five tries, fifteen minutes (`BR-CWP-023`).
FORM_UPDATE_EMAIL = "update_email"
MAX_TRIES = lockout.MAX_WRONG_ATTEMPTS

#: The four kinds of code row this flow writes. `purpose` is a plain text
#: column with no CHECK (models.py says so), so no migration is needed.
PURPOSE_MATCH = "email_update_match"
PURPOSE_PROVE = "email_update_prove"
PURPOSE_CONFIRM = "email_update_confirm"

#: Template codes — the notifications catalogue owns their palettes and the
#: seeded wording (`apps/notifications/portal_email_update_templates.py`).
TEMPLATE_CONFIRM_CODE = "portal_email_change_code"
#: The code to a contact ON FILE is the enrolment code's own template, queued by
#: `credentials.queue_code`; its wording is seeded here on first use.
TEMPLATE_ON_FILE_CODE = "portal_enrolment_code"
TEMPLATE_CHANGED_NOTICE = "portal_email_changed_notice"

#: Answer keys (never sentences).
NOT_MATCHED = "not_matched"
LOCKED = "locked"
NO_CONTACT = "no_contact_on_file"
GONE = "start_again"
NEXT_RESET = "check_email"
NEXT_ENROL = "enrol"


def _digest(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def bound_secret(code: str, email: str) -> str:
    """What the confirmation row's hash is taken over: the code AND the address.

    `credentials.verify_code` hashes whatever it is handed, so handing it this
    string is how a code typed beside a DIFFERENT address fails, with no column
    holding the pending address.
    """
    return f"{str(code or '').strip()}\n{credentials.normalise_email(email)}"


# ═══════════════════════════════════════════════════════════════════════════
# Reads
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Option:
    key: str
    channel: str
    masked: str
    destination: str


def option_salt(row_id: Any) -> str:
    """The key an option is hashed under: the server's secret and this match.

    Derived and never stored, so nothing on the row or in the browser turns back
    into a number, and a key from one match is useless in another.
    """
    return hmac.new(
        str(settings.SECRET_KEY).encode(), f"cr189-options:{row_id}".encode(), hashlib.sha256
    ).hexdigest()


def contact_options(tenant_id: Any, account: Any, salt: str) -> list[Option]:
    """Every phone and email ON FILE for this account, masked, in a stable order.

    The order is primary first, then oldest. That is `credentials.contact_for`'s
    order, so the first option is the one enrolment would have used. The key is
    an HMAC of the destination under the match row's own salt. It means nothing
    outside this one match and cannot be reversed to a number.
    """
    rows = customers_models.Contact.objects.filter(
        tenant_id=tenant_id, account_id=getattr(account, "pk", account), deleted_at__isnull=True
    ).order_by("-is_primary", "created_at")
    seen: set[str] = set()
    options: list[Option] = []
    for row in rows:
        for channel, value in ((models.CHANNEL_SMS, row.phone), (models.CHANNEL_EMAIL, row.email)):
            raw = str(value or "").strip()
            if not raw:
                continue
            ident = raw.lower()
            if ident in seen:
                continue
            seen.add(ident)
            masked = (
                credentials.mask_phone(raw)
                if channel == models.CHANNEL_SMS
                else credentials.mask_email(raw)
            )
            key = hmac.new(salt.encode(), ident.encode(), hashlib.sha256).hexdigest()[:16]
            options.append(Option(key=key, channel=channel, masked=masked, destination=raw))
    return options


def office_contact(tenant_id: Any) -> dict[str, Any]:
    """The utility's phone and opening hours, from Settings and never typed in.

    The phone is Company → Profile's support phone; the hours are the portal
    settings' own office-hours line (what the guest front page already shows).
    Either may be `None` and the screen leaves that line out.
    """
    view = selectors.settings_view(tenant_id)
    return {
        "phone": tenancy_seam.support_phone(tenant_id),
        "hours": view.get("office_hours_text") or None,
    }


def _live_row(tenant_id: Any, ref: Any, purpose: str, *, consumed: bool) -> Any:
    """One code row of this flow, still within its lifetime, or None."""
    try:
        row = credentials.code_row(tenant_id, ref)
    except Exception:  # a malformed ref is a missing one, never a 500
        return None
    if row is None or row.purpose != purpose or row.account_id is None:
        return None
    if row.superseded_at is not None:
        return None
    if consumed and row.consumed_at is None:
        return None
    if not consumed and row.consumed_at is not None:
        return None
    # A proven row's ten minutes run from when it was PROVEN, so a person who
    # typed the code at minute nine still has time to type their new address.
    clock = row.consumed_at if consumed else row.created_at
    if clock + timedelta(minutes=models.CODE_TTL_MINUTES) <= timezone.now():
        return None
    return row


def _customer_of(tenant_id: Any, account: Any) -> Any:
    link = (
        customers_models.CustomerAccount.live(
            tenant_id=tenant_id, account_id=getattr(account, "pk", account)
        )
        .select_related("customer")
        .first()
    )
    return getattr(link, "customer", None)


def _credential_of(tenant_id: Any, customer: Any) -> Any:
    if customer is None:
        return None
    return models.PortalCredential.objects.filter(
        tenant_id=tenant_id, customer_id=customer.pk
    ).first()


def _address_taken_by_someone_else(tenant_id: Any, email: str, customer: Any) -> bool:
    other = credentials.credential_by_email(tenant_id, email)
    return other is not None and (customer is None or other.customer_id != customer.pk)


# ═══════════════════════════════════════════════════════════════════════════
# Step 1 — the three facts
# ═══════════════════════════════════════════════════════════════════════════


def find(tenant_id: Any, *, address: str, account_no: Any, postcode: Any, name: Any) -> dict:
    tenant_key = str(tenant_id)
    if lockout.is_locked(tenant_key, FORM_UPDATE_EMAIL, address):
        return {"matched": False, "reason": LOCKED}
    account = credentials.find_account(
        tenant_id, account_no=account_no, postcode=postcode, name=name
    )
    if account is None:
        tries = lockout.record_wrong(tenant_key, FORM_UPDATE_EMAIL, address, max_attempts=MAX_TRIES)
        return {"matched": False, "reason": LOCKED if tries >= MAX_TRIES else NOT_MATCHED}
    lockout.clear(tenant_key, FORM_UPDATE_EMAIL, address)

    if not contact_options(tenant_id, account, "probe"):
        # BR-CWP-034, by PO ruling 2026-10-22: a dead end with the office's
        # number. No ref is handed out, so there is nothing to go on with.
        return {
            "matched": True,
            "reason": NO_CONTACT,
            "ref": None,
            "office": office_contact(tenant_id),
        }
    issued = credentials.issue_code(
        tenant_id,
        purpose=PURPOSE_MATCH,
        account=account,
        channel=models.CHANNEL_EMAIL,
        masked="",
    )
    options = contact_options(tenant_id, account, option_salt(issued.row_id))
    return {
        "matched": True,
        "ref": issued.row_id,
        "options": [
            {"key": option.key, "channel": option.channel, "masked": option.masked}
            for option in options
        ],
        "office": office_contact(tenant_id),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Steps 2 and 3 — a code to the contact on file
# ═══════════════════════════════════════════════════════════════════════════


def send_code(tenant_id: Any, *, ref: Any, option_key: Any) -> dict:
    match = _live_row(tenant_id, ref, PURPOSE_MATCH, consumed=False)
    if match is None:
        return {"sent": False, "reason": GONE}
    options = contact_options(tenant_id, match.account_id, option_salt(match.pk))
    chosen = next((one for one in options if one.key == str(option_key or "")), None)
    if chosen is None:
        return {"sent": False, "reason": GONE}
    issued = credentials.issue_code(
        tenant_id,
        purpose=PURPOSE_PROVE,
        account=match.account,
        channel=chosen.channel,
        masked=chosen.masked,
    )
    _ensure_wording(TEMPLATE_ON_FILE_CODE)
    credentials.queue_code(
        tenant_id, account=match.account, issued=issued, destination=chosen.destination
    )
    _send_instantly(tenant_id, issued.row_id)
    audit.write_row(
        action="portal_credential.email_update_code_sent",
        entity_type="account",
        entity_id=match.account_id,
        after={"actor": "portal:locked-out", "sent_to": chosen.masked, "channel": chosen.channel},
    )
    return {
        "sent": True,
        "ref": issued.row_id,
        "sent_to": chosen.masked,
        "channel": chosen.channel,
        "expires_in_minutes": models.CODE_TTL_MINUTES,
    }


def verify_code(tenant_id: Any, *, ref: Any, code: Any) -> dict:
    row = credentials.code_row(tenant_id, ref) if ref else None
    if row is None or row.purpose != PURPOSE_PROVE or row.account_id is None:
        return {"result": credentials.CODE_WRONG}
    verdict = credentials.verify_code(
        tenant_id, purpose=PURPOSE_PROVE, code=str(code or "").strip(), account=row.account
    )
    return {"result": verdict}


# ═══════════════════════════════════════════════════════════════════════════
# Step 4 — a code to the NEW address
# ═══════════════════════════════════════════════════════════════════════════


def start_confirmation(tenant_id: Any, *, ref: Any, email: Any) -> dict:
    proven = _live_row(tenant_id, ref, PURPOSE_PROVE, consumed=True)
    if proven is None:
        return {"ok": False, "reason": GONE}
    refused = _email_refusal(email)
    if refused is not None:
        return {"ok": False, "reason": refused}
    new_email = credentials.normalise_email(email)
    customer = _customer_of(tenant_id, proven.account_id)
    masked = credentials.mask_email(new_email)
    issued = credentials.issue_code(
        tenant_id,
        purpose=PURPOSE_CONFIRM,
        account=proven.account,
        channel=models.CHANNEL_EMAIL,
        masked=masked,
    )
    taken = _address_taken_by_someone_else(tenant_id, new_email, customer)
    # Bound to the address; an address that is another login's is bound to a
    # secret nobody holds, so its confirmation can never succeed.
    secret = secrets.token_urlsafe(32) if taken else issued.code
    models.PortalOneTimeCode.objects.filter(pk=issued.row_id).update(
        code_hash=_digest(bound_secret(secret, new_email))
    )
    if taken:
        credentials.equalise_timing()
        audit.write_row(
            action="portal_credential.email_update_refused",
            entity_type="account",
            entity_id=proven.account_id,
            after={
                "actor": "portal:locked-out",
                "email": masked,
                "reason": "not sent: the address is another customer's portal login",
            },
        )
    else:
        _ensure_wording(TEMPLATE_CONFIRM_CODE)
        write = notifications_seam.queue_document(
            source_type=notifications_seam.SOURCE_PORTAL,
            template=notifications_seam.template_pin(TEMPLATE_CONFIRM_CODE),
            source_id=issued.row_id,
            channels=(notifications_seam.CHANNEL_EMAIL,),
            account_id=proven.account_id,
            recipients=(
                notifications_seam.recipient(
                    channel=notifications_seam.CHANNEL_EMAIL, address=new_email
                ),
            ),
            render_context={
                "customer_name": getattr(customer, "display_name", None),
                "code": issued.code,
                "purpose": TEMPLATE_CONFIRM_CODE,
            },
            language=_utility_language(tenant_id),
        )
        _attach(tenant_id, issued.row_id, write)
        _send_instantly(tenant_id, issued.row_id, write=write)
    return {
        "ok": True,
        "ref": issued.row_id,
        "sent_to": masked,
        "expires_in_minutes": models.CODE_TTL_MINUTES,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Step 5 — confirmed: the change, the notice, the reset link
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class _Actor:
    """Who did it, for the contact write's audit row. Not a staff user."""

    customer_id: Any
    session_id: Any = None


def confirm(tenant_id: Any, *, ref: Any, code: Any, email: Any) -> dict:
    row = credentials.code_row(tenant_id, ref) if ref else None
    if row is None or row.purpose != PURPOSE_CONFIRM or row.account_id is None:
        return {"ok": False, "reason": credentials.CODE_WRONG}
    new_email = credentials.normalise_email(email)
    verdict = credentials.verify_code(
        tenant_id,
        purpose=PURPOSE_CONFIRM,
        code=bound_secret(str(code or ""), new_email),
        account=row.account,
    )
    if verdict != credentials.CODE_OK:
        return {"ok": False, "reason": verdict}

    customer = _customer_of(tenant_id, row.account_id)
    if customer is None or _address_taken_by_someone_else(tenant_id, new_email, customer):
        # Raced: another login took the address after the code went out.
        return {"ok": False, "reason": credentials.CODE_WRONG}

    with transaction.atomic():
        # One proof buys one change: every live row of this flow for the
        # account is retired, so the proven code cannot start a second one.
        models.PortalOneTimeCode.objects.filter(
            tenant_id=tenant_id,
            account_id=row.account_id,
            purpose__in=(PURPOSE_MATCH, PURPOSE_PROVE, PURPOSE_CONFIRM),
            superseded_at__isnull=True,
        ).update(superseded_at=timezone.now())
        credential = _credential_of(tenant_id, customer)
        on_file = str(getattr(_primary_contact(tenant_id, row.account_id), "email", "") or "")
        old_email = credential.email if credential is not None else on_file
        account_ids = [
            str(link.account_id)
            for link in customers_models.CustomerAccount.live(
                tenant_id=tenant_id, customer_id=customer.pk
            )
        ] or [str(row.account_id)]
        services.update_own_contact_details(
            tenant_id,
            actor=_Actor(customer_id=customer.pk),
            account_ids=account_ids,
            payload={"email": new_email},
        )
        if credential is not None and credential.email != new_email:
            credential.email = new_email
            credential.save(update_fields=["email", "updated_at"])
        audit.write_row(
            action="portal_credential.email_changed",
            entity_type="portal_credential" if credential is not None else "customer",
            entity_id=credential.pk if credential is not None else customer.pk,
            before={"email": credentials.mask_email(old_email) if old_email else None},
            after={
                "actor": "portal:locked-out",
                "email": credentials.mask_email(new_email),
                "verified_by": "code to a contact on file, then a code to the new address",
                "accounts_updated": len(account_ids),
            },
        )
        if old_email and credentials.normalise_email(old_email) != new_email:
            _queue_changed_notice(
                tenant_id,
                source_id=uuid.uuid5(uuid.UUID(str(row.pk)), "changed-notice"),
                account_id=row.account_id,
                customer=customer,
                old_email=old_email,
                new_email=new_email,
            )
        if credential is None:
            return {"ok": True, "next": NEXT_ENROL, "sent_to": credentials.mask_email(new_email)}
        _send_reset(tenant_id, credential)
    return {"ok": True, "next": NEXT_RESET, "sent_to": credentials.mask_email(new_email)}


def _primary_contact(tenant_id: Any, account_id: Any) -> Any:
    return (
        customers_models.Contact.objects.filter(
            tenant_id=tenant_id, account_id=account_id, deleted_at__isnull=True
        )
        .order_by("-is_primary", "created_at")
        .first()
    )


def _queue_changed_notice(
    tenant_id, *, source_id, account_id, customer, old_email, new_email
) -> None:
    """`portal_email_changed_notice` to the OLD address, instantly.

    `source_id` names the act that moved the login (derived from the CONFIRM
    code row, or a fresh id for a clerk's tick), so the notice is its own queue
    row and a second change on another day is a second notice. One function for all three doors: the
    locked-out confirm, the signed-in confirm and the clerk's tick
    (decision log 2026-10-22, lane SIGNIN-EMAIL item 11).
    """
    _ensure_wording(TEMPLATE_CHANGED_NOTICE)
    write = notifications_seam.queue_document(
        source_type=notifications_seam.SOURCE_PORTAL,
        template=notifications_seam.template_pin(TEMPLATE_CHANGED_NOTICE),
        source_id=source_id,
        channels=(notifications_seam.CHANNEL_EMAIL,),
        account_id=account_id,
        recipients=(
            notifications_seam.recipient(
                channel=notifications_seam.CHANNEL_EMAIL, address=old_email
            ),
        ),
        render_context={
            "customer_name": getattr(customer, "display_name", None),
            "new_email_masked": credentials.mask_email(new_email),
            "purpose": TEMPLATE_CHANGED_NOTICE,
        },
        language=_utility_language(tenant_id),
    )
    _send_instantly(tenant_id, None, write=write)


def _send_reset(tenant_id: Any, credential: Any) -> None:
    """The forgot-password link, through the ONE reset issuer.

    `credentials.send_reset` is PORTAL-RESET's (DEF-CWP-10381): it builds the
    absolute link from PUBLIC_APP_ORIGIN (the secret in the URL FRAGMENT, never
    the query string — decision log 2026-10-22, MERGE-ACCESS), queues
    `portal_password_reset` and sends instantly. With no public address it
    mints nothing and writes its own audit line. The pre-merge fallback that
    called `issue_code` + `queue_reset` directly was removed at merge: it built
    no link at all.
    """
    credentials.send_reset(tenant_id, credential=credential)


# ═══════════════════════════════════════════════════════════════════════════
# The clerk's tick — "Also use this as the portal sign-in email"
# (PO 2026-10-22, closes OQ-CUS-12350; DEF-CWP-10400)
# ═══════════════════════════════════════════════════════════════════════════

#: What `staff_move_sign_in` answers. Keys, never sentences; the customers
#: module turns the refusals into field errors the clerk reads.
STAFF_MOVED = "moved"
STAFF_UNCHANGED = "unchanged"
STAFF_NO_LOGIN = "no_login"
STAFF_TAKEN = "taken"


def live_credential_of(tenant_id: Any, customer_id: Any) -> Any:
    """The customer's login that can sign in, oldest first, or None.

    "Has a portal login" is the question `customers.portal_seam` answers for
    the account screen: a credential that is not disabled.
    """
    return (
        models.PortalCredential.objects.filter(tenant_id=tenant_id, customer_id=customer_id)
        .exclude(status=models.CREDENTIAL_DISABLED)
        .order_by("enrolled_on", "id")
        .first()
    )


def staff_move_sign_in(
    tenant_id: Any, *, customer_id: Any, email: Any, actor_user_id: Any
) -> dict[str, Any]:
    """A clerk ticked the box: the login's email becomes the contact email.

    Called INSIDE the clerk's save transaction (`customers.customer_edit` and
    `customers.services.update_account_contact`, through
    `customers.portal_seam.move_portal_sign_in`), so a refusal there rolls the
    contact write back with it and nothing is half-saved.

    The checks run in the order a clerk makes mistakes: no login, nothing
    typed, a malformed address, the same address, another customer's address.
    On a move: one audit row naming the clerk, the notice to the OLD address,
    the reset link to the new one (`credentials.send_reset`, the one issuer).
    Both go to the instant sender on commit.

    ⚠ **THE SAVE IS IN A SAVEPOINT, AND THAT IS LAW 14, NOT TIDINESS.** The
    `ux_portal_credential_tenant_email` clash can still arrive between the
    check and the write (a customer enrolling the same minute). On PostgreSQL a
    failed statement poisons the whole transaction; the nested `atomic()` rolls
    back to just before the save, so the clerk's transaction survives to raise
    a sentence. SQLite cannot show this, so it is proved in
    `tests/test_cr189_signin_email_pg.py`.
    """
    credential = live_credential_of(tenant_id, customer_id)
    if credential is None:
        return {"result": STAFF_NO_LOGIN}
    refused = credentials.email_refusal(email)
    if refused is not None:
        return {"result": refused}
    new_email = credentials.normalise_email(email)
    old_email = credential.email
    if old_email == new_email:
        return {"result": STAFF_UNCHANGED}
    other = credentials.credential_by_email(tenant_id, new_email)
    if other is not None and other.pk != credential.pk:
        return {"result": STAFF_TAKEN}
    try:
        with transaction.atomic():
            credential.email = new_email
            credential.save(update_fields=["email", "updated_at"])
    except IntegrityError:
        credential.email = old_email
        return {"result": STAFF_TAKEN}
    audit.write_row(
        action="portal_credential.email_changed",
        entity_type="portal_credential",
        entity_id=credential.pk,
        actor_user_id=actor_user_id,
        before={"email": credentials.mask_email(old_email)},
        after={
            "actor": "staff",
            "email": credentials.mask_email(new_email),
            "verified_by": "a clerk ticked 'Also use this as the portal sign-in email'",
        },
    )
    first_account = (
        customers_models.CustomerAccount.live(tenant_id=tenant_id, customer_id=customer_id)
        .values_list("account_id", flat=True)
        .first()
    )
    _queue_changed_notice(
        tenant_id,
        source_id=uuid.uuid4(),
        account_id=first_account,
        customer=getattr(credential, "customer", None),
        old_email=old_email,
        new_email=new_email,
    )
    credentials.send_reset(tenant_id, credential=credential)
    return {"result": STAFF_MOVED, "sent_to": credentials.mask_email(new_email)}


# ═══════════════════════════════════════════════════════════════════════════
# The signed-in change — a code to the NEW address, then both move
# (PO 2026-10-22, option A; DEF-CWP-10401)
# ═══════════════════════════════════════════════════════════════════════════

#: The code row's purpose. Keyed to the LOGIN (`portal_credential_id`), so a
#: second start supersedes the first and no account has to be chosen.
PURPOSE_SIGNED_IN = "email_update_signed_in"
UNCHANGED = "unchanged"


def _signed_in_credential(principal: Any) -> Any:
    return models.PortalCredential.objects.filter(
        tenant_id=principal.tenant_id, pk=principal.credential_id
    ).first()


def start_signed_in_change(principal: Any, *, email: Any) -> dict[str, Any]:
    """Step 1 of 2 — a code to the address the signed-in customer typed.

    Nothing is stored but the code row, whose hash is bound to the address
    (`bound_secret`), exactly as the locked-out flow's step 4. An address that
    is ANOTHER customer's login gets the identical answer and no code: a
    signed-in customer could otherwise ask *"does this address bank online
    here?"* one address at a time.
    """
    tenant_id = principal.tenant_id
    refused = _email_refusal(email)
    if refused is not None:
        return {"ok": False, "reason": refused}
    credential = _signed_in_credential(principal)
    if credential is None:
        return {"ok": False, "reason": GONE}
    new_email = credentials.normalise_email(email)
    if new_email == credential.email:
        return {"ok": False, "reason": UNCHANGED}
    masked = credentials.mask_email(new_email)
    issued = credentials.issue_code(
        tenant_id,
        purpose=PURPOSE_SIGNED_IN,
        credential=credential,
        channel=models.CHANNEL_EMAIL,
        masked=masked,
    )
    taken = credentials.credential_by_email(tenant_id, new_email) is not None
    secret = secrets.token_urlsafe(32) if taken else issued.code
    models.PortalOneTimeCode.objects.filter(pk=issued.row_id).update(
        code_hash=_digest(bound_secret(secret, new_email))
    )
    if taken:
        credentials.equalise_timing()
        audit.write_row(
            action="portal_credential.email_update_refused",
            entity_type="portal_credential",
            entity_id=credential.pk,
            after={
                "actor": "portal:signed-in",
                "email": masked,
                "reason": "not sent: the address is another customer's portal login",
            },
        )
    else:
        _ensure_wording(TEMPLATE_CONFIRM_CODE)
        write = notifications_seam.queue_document(
            source_type=notifications_seam.SOURCE_PORTAL,
            template=notifications_seam.template_pin(TEMPLATE_CONFIRM_CODE),
            source_id=issued.row_id,
            channels=(notifications_seam.CHANNEL_EMAIL,),
            account_id=next(iter(principal.account_ids), None),
            recipients=(
                notifications_seam.recipient(
                    channel=notifications_seam.CHANNEL_EMAIL, address=new_email
                ),
            ),
            render_context={
                "customer_name": getattr(credential.customer, "display_name", None),
                "code": issued.code,
                "purpose": TEMPLATE_CONFIRM_CODE,
            },
            language=_utility_language(tenant_id),
        )
        _attach(tenant_id, issued.row_id, write)
        _send_instantly(tenant_id, issued.row_id, write=write)
    return {
        "ok": True,
        "ref": issued.row_id,
        "sent_to": masked,
        "expires_in_minutes": models.CODE_TTL_MINUTES,
    }


def confirm_signed_in_change(principal: Any, *, ref: Any, code: Any, email: Any) -> dict[str, Any]:
    """Step 2 of 2 — the code came back: the contact email AND the login move.

    The contact rows move through the `contact_detail` write point on every
    account in the SESSION (`BR-CWP-010`: the set is the session's, never a
    body's). The old sign-in address gets the notice. No reset link: the
    customer is signed in and knows their password.
    """
    tenant_id = principal.tenant_id
    credential = _signed_in_credential(principal)
    row = credentials.code_row(tenant_id, ref) if ref else None
    if (
        credential is None
        or row is None
        or row.purpose != PURPOSE_SIGNED_IN
        or str(row.portal_credential_id) != str(credential.pk)
    ):
        return {"ok": False, "reason": credentials.CODE_WRONG}
    new_email = credentials.normalise_email(email)
    verdict = credentials.verify_code(
        tenant_id,
        purpose=PURPOSE_SIGNED_IN,
        code=bound_secret(str(code or ""), new_email),
        credential=credential,
    )
    if verdict != credentials.CODE_OK:
        return {"ok": False, "reason": verdict}
    if _address_taken_by_someone_else(tenant_id, new_email, credential.customer):
        # Raced: another login took the address after the code went out.
        return {"ok": False, "reason": credentials.CODE_WRONG}

    with transaction.atomic():
        old_email = credential.email
        result = services.update_own_contact_details(
            tenant_id,
            actor=principal,
            account_ids=list(principal.account_ids),
            payload={"email": new_email},
        )
        if old_email != new_email:
            credential.email = new_email
            credential.save(update_fields=["email", "updated_at"])
        audit.write_row(
            action="portal_credential.email_changed",
            entity_type="portal_credential",
            entity_id=credential.pk,
            before={"email": credentials.mask_email(old_email) if old_email else None},
            after={
                "actor": "portal:signed-in",
                "email": credentials.mask_email(new_email),
                "verified_by": "a code to the new address",
                "accounts_updated": result.get("accounts_updated", 0),
            },
        )
        if old_email and old_email != new_email:
            _queue_changed_notice(
                tenant_id,
                source_id=uuid.uuid5(uuid.UUID(str(row.pk)), "changed-notice"),
                account_id=next(iter(principal.account_ids), None),
                customer=credential.customer,
                old_email=old_email,
                new_email=new_email,
            )
    return {
        "ok": True,
        "accounts_updated": result.get("accounts_updated", 0),
        "sent_to": credentials.mask_email(new_email),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Small helpers
# ═══════════════════════════════════════════════════════════════════════════


def _email_refusal(value: Any) -> str | None:
    """A statement about what was TYPED, never about what is stored — the ONE
    check the forgot-password door uses (`credentials.email_refusal`,
    DEF-CWP-10380)."""
    return credentials.email_refusal(value)


def _utility_language(tenant_id: Any) -> str | None:
    """The utility's Regional default language (2026-09-23: emails go in it)."""
    try:
        return tenancy_seam.regional(tenant_id).get("language") or None
    except Exception:  # pragma: no cover — a missing setting is no language
        return None


def _attach(tenant_id: Any, row_id: Any, write: Any) -> None:
    row = credentials.code_row(tenant_id, row_id)
    message_id = notifications_seam.first_message_id(write)
    if row is not None and message_id is not None:
        credentials.attach_outbound(row, message_id)


def _message_ids(tenant_id: Any, row_id: Any, write: Any) -> list[Any]:
    if write is not None:
        return [message.id for message in (getattr(write, "messages", None) or ())]
    row = credentials.code_row(tenant_id, row_id) if row_id else None
    return [row.outbound_message_id] if row is not None and row.outbound_message_id else []


def _send_instantly(tenant_id: Any, row_id: Any, *, write: Any = None) -> None:
    """Account-access mail goes the moment the transaction commits (PO 2026-10-22).

    `notifications.services.send_now(message_ids, actor=None)`, resolved BY
    NAME through the seam (G81: the portal never imports `services`). It marks
    the rows highest priority and hands them to the instant sender on commit
    itself, so nothing is sent inside this request. Absent ⇒ nothing happens
    and the row waits for the normal cycle, which is the ruling's own fallback.
    """
    ids = _message_ids(tenant_id, row_id, write)
    fn = notifications_seam._resolve("send_now")
    if ids and fn is not None:
        fn(ids)


def _ensure_wording(code: str) -> None:
    """Plant the template's default and language variants if this utility lacks
    them (`seed_templates.ensure_seeded`, insert-missing). Absent ⇒ no-op; the
    queue row then holds with notifications' own *no published template*
    reason, never with wording from here."""
    fn = notifications_seam._resolve("ensure_seeded", kind="seed_templates")
    if fn is not None:
        fn(code)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-189-BRC10 + decision log 2026-10-22 (four entries) + BR-CWP-023/030/031/033/034/035
# generated: 2026-10-22 by lane PORTAL-EMAIL
# checklist: A✔ B✔ C✔ D✔(email_update_api.py) E✔(UpdateEmail.tsx) F✔ G✔ H=PENDING(🔒 — which address a reset link reaches)
# gates: G81/G84 (declared in write_points.py with PortalCredential + PortalOneTimeCode) · G91 · G96
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
